"""Formulários do módulo de reserva de garagem."""

from __future__ import annotations

from datetime import date, timedelta

from django import forms
from django.contrib.auth.models import Group
from django.db import models
from django.db.models import Q

from setores.services import user_display_name
from usuarios.services import visible_users_queryset

from .models import ConfiguracaoReservaGaragem, ReservaGaragem, VagaGaragem


BOOTSTRAP_INPUT = "form-control form-control-lg"
BOOTSTRAP_TEXTAREA = "form-control"


def _datas_periodo(data_inicial: date, data_final: date, recorrencia: str = "") -> list[date]:
    """Expande o período em datas concretas, respeitando a recorrência útil quando aplicada."""

    if not data_inicial:
        return []
    if not data_final:
        return [data_inicial]

    datas = []
    cursor = data_inicial
    while cursor <= data_final:
        if recorrencia == ReservaGaragemSolicitacaoForm.Recorrencia.DIAS_UTEIS and cursor.weekday() >= 5:
            cursor += timedelta(days=1)
            continue
        datas.append(cursor)
        cursor += timedelta(days=1)
    return datas


def vagas_disponiveis_no_periodo(
    data_inicial: date | None,
    data_final: date | None,
    recorrencia: str = "",
    *,
    reserva_atual: ReservaGaragem | None = None,
):
    """Retorna somente as vagas ativas sem reserva deferida em nenhuma data do período."""

    vagas = VagaGaragem.objects.filter(ativo=True).order_by("nome")
    if reserva_atual and reserva_atual.pk:
        vagas = VagaGaragem.objects.filter(Q(pk=reserva_atual.vaga_id) | Q(ativo=True)).order_by("nome")

    datas = _datas_periodo(data_inicial, data_final, recorrencia)
    if not datas:
        return vagas.none()

    conflitos = ReservaGaragem.objects.filter(
        data__in=datas,
        status=ReservaGaragem.Status.DEFERIDA,
    )
    if reserva_atual and reserva_atual.pk:
        conflitos = conflitos.exclude(pk=reserva_atual.pk)
        if reserva_atual.serie_id:
            conflitos = conflitos.exclude(serie_id=reserva_atual.serie_id)
    return vagas.exclude(pk__in=conflitos.values_list("vaga_id", flat=True)).distinct()


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes Bootstrap consistentes com o restante do portal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select form-select-lg"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                css = BOOTSTRAP_TEXTAREA
            else:
                css = BOOTSTRAP_INPUT
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {css}".strip()


class VagaGaragemForm(BootstrapModelForm):
    """CRUD das vagas disponíveis para reserva."""

    class Meta:
        model = VagaGaragem
        fields = ["nome", "localizacao", "cor", "ativo"]
        widgets = {
            "cor": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
        }


class ConfiguracaoReservaGaragemForm(BootstrapModelForm):
    """Permite definir o grupo operacional de fiscais do módulo."""

    class Meta:
        model = ConfiguracaoReservaGaragem
        fields = ["grupo_fiscais"]
        widgets = {"grupo_fiscais": forms.Select(attrs={"class": "form-select form-select-lg"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo_fiscais"].queryset = Group.objects.order_by("name")
        self.fields["grupo_fiscais"].required = False
        self.fields["grupo_fiscais"].help_text = "Usuários desse grupo poderão deferir e indeferir as solicitações."


class ReservaGaragemSolicitacaoForm(BootstrapModelForm):
    """Formulário do solicitante com suporte a série por intervalo e recorrência."""

    class Recorrencia(models.TextChoices):
        NENHUMA = "", "Sem recorrência"
        DIARIA = "daily", "Diária (dias corridos)"
        DIAS_UTEIS = "business_daily", "Diária (dias úteis)"

    data_inicial = forms.DateField(
        label="Data inicial",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    data_final = forms.DateField(
        label="Data final",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    recorrencia = forms.ChoiceField(
        label="Recorrência",
        required=False,
        choices=Recorrencia.choices,
    )
    responsavel = forms.CharField(
        label="Nome do usuário",
        required=False,
        max_length=180,
    )

    class Meta:
        model = ReservaGaragem
        fields = [
            "vaga",
            "marca_veiculo",
            "modelo_veiculo",
            "cor_veiculo",
            "placa_veiculo",
            "observacoes",
        ]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        self.modo_fiscal = kwargs.pop("modo_fiscal", False)
        super().__init__(*args, **kwargs)
        self.tem_periodo_informado = False
        self.tem_vagas_disponiveis = False
        self.mensagem_sem_vagas = ""
        self.mostrar_responsavel_campo = self.modo_fiscal
        self.usuarios_responsaveis_sugestoes = []
        self.usuario_responsavel_resolvido = None

        if self.instance and self.instance.pk:
            self.initial["data_inicial"] = self.instance.data
            self.initial["data_final"] = self.instance.data
            self.initial["responsavel"] = self.instance.responsavel
            self.fields["recorrencia"].disabled = True

        data_inicial, data_final, recorrencia = self._periodo_atual()
        vagas = vagas_disponiveis_no_periodo(
            data_inicial,
            data_final,
            recorrencia,
            reserva_atual=self.instance if self.instance and self.instance.pk else None,
        )

        self.tem_periodo_informado = bool(data_inicial and data_final)
        self.tem_vagas_disponiveis = vagas.exists()
        if self.tem_periodo_informado and not self.tem_vagas_disponiveis:
            self.mensagem_sem_vagas = (
                f"Não há vagas para o período de {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y}"
            )

        self.fields["vaga"].queryset = vagas
        self.fields["vaga"].label_from_instance = lambda obj: obj.nome_exibicao
        self.fields["vaga"].widget.attrs["data-selected-value"] = str(self.initial.get("vaga") or "")
        self.fields["data_inicial"].input_formats = ["%Y-%m-%d"]
        self.fields["data_final"].input_formats = ["%Y-%m-%d"]
        self._configurar_campo_responsavel()
        if self.instance and self.instance.pk and self.instance.serie_id:
            self.fields["data_inicial"].disabled = True
            self.fields["data_final"].disabled = True

    def _configurar_campo_responsavel(self) -> None:
        """Ajusta o campo de responsável conforme o modo comum ou o fluxo fiscal pré-definido."""

        if not self.modo_fiscal:
            self.fields["responsavel"].initial = self.get_responsavel_padrao()
            self.fields["responsavel"].widget = forms.HiddenInput()
            return

        usuarios = list(visible_users_queryset().select_related("perfil").order_by("first_name", "username"))
        self.usuarios_responsaveis_sugestoes = [
            {
                "nome": user_display_name(usuario),
                "username": usuario.username,
                "email": usuario.email or "",
            }
            for usuario in usuarios
        ]
        self.fields["responsavel"].required = True
        self.fields["responsavel"].help_text = "Selecione um usuário sugerido ou digite o nome manualmente."
        self.fields["responsavel"].widget.attrs["list"] = "reserva-garagem-responsaveis"
        self.fields["responsavel"].widget.attrs["autocomplete"] = "off"
        if not self.initial.get("responsavel") and self.request_user:
            self.fields["responsavel"].initial = self.get_responsavel_padrao()

    def get_responsavel_padrao(self) -> str:
        """Retorna o nome humano padrão do usuário logado para gravação automática."""

        if not self.request_user:
            return ""
        perfil = getattr(self.request_user, "perfil", None)
        return (getattr(perfil, "nome_completo", "") or self.request_user.get_full_name() or self.request_user.username).strip()

    def _periodo_atual(self) -> tuple[date | None, date | None, str]:
        """Lê o período atual a partir do POST/GET inicial para montar as vagas disponíveis."""

        recorrencia = ""
        if self.is_bound:
            data_inicial = self._parse_date_value(self.data.get(self.add_prefix("data_inicial")))
            data_final = self._parse_date_value(self.data.get(self.add_prefix("data_final")))
            recorrencia = (self.data.get(self.add_prefix("recorrencia")) or "").strip()
            return data_inicial, data_final, recorrencia

        data_inicial = self.initial.get("data_inicial")
        data_final = self.initial.get("data_final")
        if isinstance(data_inicial, str):
            data_inicial = self._parse_date_value(data_inicial)
        if isinstance(data_final, str):
            data_final = self._parse_date_value(data_final)
        recorrencia = (self.initial.get("recorrencia") or "").strip()
        return data_inicial, data_final, recorrencia

    @staticmethod
    def _parse_date_value(value) -> date | None:
        """Converte datas ISO do formulário em objetos `date` de forma tolerante."""

        if isinstance(value, date):
            return value
        if not value:
            return None
        try:
            return date.fromisoformat(str(value))
        except ValueError:
            return None

    def get_recurrence_dates(self):
        """Expande a data base nas ocorrências diárias contínuas ou em dias úteis."""

        data_inicial = self.cleaned_data.get("data_inicial")
        data_final = self.cleaned_data.get("data_final")
        recorrencia = self.cleaned_data.get("recorrencia") or ""
        return _datas_periodo(data_inicial, data_final, recorrencia)

    def _resolver_usuario_por_nome(self, responsavel: str):
        """Relaciona o texto informado a um usuário humano quando houver correspondência exata."""

        termo = (responsavel or "").strip().casefold()
        if not termo:
            return None
        for usuario in visible_users_queryset().select_related("perfil").order_by("first_name", "username"):
            candidatos = {
                user_display_name(usuario).strip().casefold(),
                usuario.username.strip().casefold(),
                (usuario.email or "").strip().casefold(),
            }
            if termo in candidatos:
                return usuario
        return None

    def validate_series_update_conflicts(self, instance: ReservaGaragem) -> None:
        """Valida conflitos nas mesmas datas da série ao editar com escopo total."""

        if not instance.serie_id:
            return
        vaga = self.cleaned_data.get("vaga")
        placa = (self.cleaned_data.get("placa_veiculo") or "").strip().upper()
        if not (vaga and placa):
            return
        ocorrencias = ReservaGaragem.objects.filter(serie_id=instance.serie_id).order_by("data")
        for ocorrencia in ocorrencias:
            conflitos_vaga = ReservaGaragem.objects.filter(
                vaga=vaga,
                data=ocorrencia.data,
                status=ReservaGaragem.Status.DEFERIDA,
            ).exclude(serie_id=instance.serie_id)
            if conflitos_vaga.exists():
                raise forms.ValidationError("A vaga escolhida já possui reserva deferida em uma das datas da série.")
            conflitos_placa = ReservaGaragem.objects.filter(
                placa_veiculo__iexact=placa,
                data=ocorrencia.data,
            ).exclude(serie_id=instance.serie_id).exclude(status=ReservaGaragem.Status.CANCELADA)
            if conflitos_placa.exists():
                raise forms.ValidationError("A placa informada já possui reserva em uma das datas da série.")

    def clean(self):
        cleaned = super().clean()
        vaga = cleaned.get("vaga")
        data_inicial = cleaned.get("data_inicial")
        data_final = cleaned.get("data_final")
        placa = (cleaned.get("placa_veiculo") or "").strip().upper()
        responsavel = (cleaned.get("responsavel") or "").strip()
        cleaned["placa_veiculo"] = placa
        cleaned["responsavel"] = responsavel or self.get_responsavel_padrao()
        self.usuario_responsavel_resolvido = self._resolver_usuario_por_nome(cleaned["responsavel"])

        if self.modo_fiscal and not responsavel:
            self.add_error("responsavel", "Informe o nome do usuário responsável.")

        if data_inicial and data_final and data_final < data_inicial:
            self.add_error("data_final", "A data final deve ser maior ou igual à data inicial.")

        if self.instance and self.instance.pk and not self.instance.pode_editar_solicitante:
            raise forms.ValidationError("Esta solicitação não pode mais ser alterada pelo solicitante.")

        if vaga and data_inicial and data_final:
            for occ_date in self.get_recurrence_dates():
                conflitos_vaga = ReservaGaragem.objects.filter(
                    vaga=vaga,
                    data=occ_date,
                    status=ReservaGaragem.Status.DEFERIDA,
                ).exclude(pk=self.instance.pk)
                if conflitos_vaga.exists():
                    self.add_error(None, "Já existe reserva deferida para a vaga em uma das datas informadas.")
                    return cleaned

                conflitos_placa = ReservaGaragem.objects.filter(
                    placa_veiculo__iexact=placa,
                    data=occ_date,
                ).exclude(pk=self.instance.pk).exclude(status=ReservaGaragem.Status.CANCELADA)
                if conflitos_placa.exists():
                    self.add_error("placa_veiculo", "A placa informada já possui reserva em uma das datas selecionadas.")
                    return cleaned

                if not self.modo_fiscal and self.request_user and getattr(self.request_user, "is_authenticated", False):
                    conflitos_solicitante = ReservaGaragem.objects.filter(
                        solicitante=self.request_user,
                        data=occ_date,
                    ).exclude(pk=self.instance.pk).exclude(status=ReservaGaragem.Status.CANCELADA)
                    if conflitos_solicitante.exists():
                        self.add_error(None, "Você já possui reserva para uma das datas selecionadas.")
                        return cleaned
        return cleaned


class ReservaGaragemAnaliseForm(BootstrapModelForm):
    """Formulário do fiscal para deferir ou indeferir a solicitação."""

    decisao = forms.ChoiceField(
        label="Decisão",
        choices=[("DEFERIR", "Deferir"), ("INDEFERIR", "Indeferir")],
    )

    class Meta:
        model = ReservaGaragem
        fields = ["justificativa_indeferimento"]
        widgets = {"justificativa_indeferimento": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        cleaned = super().clean()
        decisao = cleaned.get("decisao")
        justificativa = (cleaned.get("justificativa_indeferimento") or "").strip()
        if decisao == "INDEFERIR" and not justificativa:
            self.add_error("justificativa_indeferimento", "Informe a justificativa do indeferimento.")
        return cleaned
