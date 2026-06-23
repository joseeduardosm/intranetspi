"""Formulários do módulo de reserva de espaços."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from django import forms
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models import Q

from setores.services import user_display_name
from usuarios.services import visible_users_queryset

from .models import ConfiguracaoReservaEspacos, ObjetoReservavel, ReservaRecurso


BOOTSTRAP_INPUT = "form-control form-control-lg"
BOOTSTRAP_TEXTAREA = "form-control"


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes visuais coerentes com o restante do portal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select form-select-lg"
            elif isinstance(field.widget, forms.SelectMultiple):
                css = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                css = BOOTSTRAP_TEXTAREA
            else:
                css = BOOTSTRAP_INPUT
            current = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{current} {css}".strip()


class ObjetoReservavelForm(BootstrapModelForm):
    """Formulário do cadastro de objetos que aparecerão no calendário."""

    class Meta:
        model = ObjetoReservavel
        fields = ["nome", "localizacao", "cor", "ativo"]
        widgets = {
            "cor": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
        }


class ConfiguracaoReservaEspacosForm(BootstrapModelForm):
    """Permite definir o grupo operacional de fiscais do módulo."""

    class Meta:
        model = ConfiguracaoReservaEspacos
        fields = ["grupo_fiscais"]
        widgets = {"grupo_fiscais": forms.Select(attrs={"class": "form-select form-select-lg"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo_fiscais"].queryset = Group.objects.order_by("name")
        self.fields["grupo_fiscais"].required = False
        self.fields["grupo_fiscais"].help_text = "Usuários desse grupo poderão deferir e indeferir as solicitações."


class ReservaRecursoForm(BootstrapModelForm):
    """Formulário de criação e edição com suporte a recorrência e fluxo fiscal."""

    conflict_error_message = "Já existe uma reserva deferida para este objeto no intervalo informado."

    recorrencia = forms.ChoiceField(
        label="Recorrência",
        required=False,
        choices=[
            ("", "Sem recorrência"),
            ("daily", "Diária"),
            ("weekly", "Semanal"),
            ("biweekly", "Quinzenal"),
            ("monthly", "Mensal"),
        ],
    )
    recorrencia_fim = forms.DateField(
        label="Data fim da recorrência",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta:
        model = ReservaRecurso
        fields = [
            "objeto",
            "data",
            "hora_inicio",
            "hora_fim",
            "titulo",
            "responsavel",
            "observacoes",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "observacoes": forms.Textarea(attrs={"rows": 4}),
        }

    @staticmethod
    def objetos_disponiveis_na_data(data_referencia, *, objeto_atual_id=None):
        """Retorna objetos ativos sem reserva deferida na data escolhida."""

        objetos = ObjetoReservavel.objects.filter(ativo=True)
        if not data_referencia:
            if objeto_atual_id:
                return ObjetoReservavel.objects.filter(Q(pk=objeto_atual_id) | Q(ativo=True)).order_by("nome").distinct()
            return objetos.none()

        ocupados_ids = ReservaRecurso.objects.filter(
            data=data_referencia,
            status=ReservaRecurso.Status.DEFERIDA,
        ).values_list("objeto_id", flat=True)
        objetos = objetos.exclude(pk__in=ocupados_ids)
        if objeto_atual_id:
            objetos = ObjetoReservavel.objects.filter(Q(pk=objeto_atual_id) | Q(pk__in=objetos.values("pk"))).distinct()
        return objetos.order_by("nome")

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        self.modo_fiscal = kwargs.pop("modo_fiscal", False)
        super().__init__(*args, **kwargs)
        self.usuarios_responsaveis_sugestoes = []
        self.usuario_responsavel_resolvido = None

        data_referencia = self.data.get("data") or self.initial.get("data") or getattr(self.instance, "data", None)
        objeto_atual_id = getattr(self.instance, "objeto_id", None)
        self.fields["objeto"].queryset = self.objetos_disponiveis_na_data(
            data_referencia,
            objeto_atual_id=objeto_atual_id,
        )
        self.fields["objeto"].label_from_instance = lambda obj: obj.nome_exibicao
        self.fields["data"].input_formats = ["%Y-%m-%d"]
        self.fields["hora_inicio"].input_formats = ["%H:%M"]
        self.fields["hora_fim"].input_formats = ["%H:%M"]
        self.fields["objeto"].help_text = "Escolha primeiro a data para listar somente os objetos disponíveis."
        if not data_referencia and not (self.instance and self.instance.pk):
            self.fields["objeto"].widget.attrs["disabled"] = True

        # O fluxo comum segue automático: o responsável sempre é o próprio usuário logado.
        if self.request_user and getattr(self.request_user, "is_authenticated", False) and not self.modo_fiscal:
            self.initial["responsavel"] = self.get_responsavel_padrao()
            self.fields["responsavel"].widget.attrs["readonly"] = True
            self.fields["responsavel"].help_text = "Preenchido automaticamente com o seu usuário."

        # O fluxo fiscal de pré-reserva permite escolher um usuário conhecido ou digitar manualmente.
        if self.modo_fiscal:
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
            self.fields["responsavel"].widget.attrs["list"] = "reserva-espacos-responsaveis"
            self.fields["responsavel"].widget.attrs["autocomplete"] = "off"
            if not self.initial.get("responsavel") and self.request_user:
                self.initial["responsavel"] = self.get_responsavel_padrao()

        if self.instance and self.instance.pk:
            self.fields["recorrencia"].disabled = True
            self.fields["recorrencia_fim"].disabled = True

    def get_responsavel_padrao(self) -> str:
        """Retorna o nome que deve ser gravado como responsável da reserva."""

        if not self.request_user:
            return ""
        perfil = getattr(self.request_user, "perfil", None)
        if perfil and perfil.nome_completo:
            return perfil.nome_completo
        return self.request_user.get_full_name() or self.request_user.username

    def is_recurring_series(self) -> bool:
        """Indica se a reserva editada já pertence a uma série existente."""

        return bool(self.instance and self.instance.pk and self.instance.serie_id)

    def _add_months(self, base_date, months: int):
        """Soma meses preservando o dia quando o mês destino suportar."""

        year = base_date.year + (base_date.month - 1 + months) // 12
        month = (base_date.month - 1 + months) % 12 + 1
        last_day = calendar.monthrange(year, month)[1]
        return base_date.replace(year=year, month=month, day=min(base_date.day, last_day))

    def get_recurrence_dates(self):
        """Expande a data base nas ocorrências da recorrência informada."""

        data = self.cleaned_data.get("data")
        recorrencia = self.cleaned_data.get("recorrencia") or ""
        recorrencia_fim = self.cleaned_data.get("recorrencia_fim")
        if not data:
            return []
        if not recorrencia:
            return [data]
        if not recorrencia_fim:
            return [data]

        dates = [data]
        current = data
        if recorrencia == "daily":
            delta = timedelta(days=1)
            while True:
                current = current + delta
                if current > recorrencia_fim:
                    break
                dates.append(current)
        elif recorrencia == "weekly":
            delta = timedelta(days=7)
            while True:
                current = current + delta
                if current > recorrencia_fim:
                    break
                dates.append(current)
        elif recorrencia == "biweekly":
            delta = timedelta(days=14)
            while True:
                current = current + delta
                if current > recorrencia_fim:
                    break
                dates.append(current)
        elif recorrencia == "monthly":
            while True:
                current = self._add_months(current, 1)
                if current > recorrencia_fim:
                    break
                dates.append(current)
        return dates

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

    def validate_series_update_conflicts(self, instance: ReservaRecurso) -> None:
        """Valida conflitos de todas as datas da série ao editar com escopo total."""

        if not instance.serie_id:
            return
        objeto = self.cleaned_data.get("objeto")
        hora_inicio = self.cleaned_data.get("hora_inicio")
        hora_fim = self.cleaned_data.get("hora_fim")
        if not (objeto and hora_inicio and hora_fim):
            return
        ocorrencias = ReservaRecurso.objects.filter(serie_id=instance.serie_id).order_by("data")
        for ocorrencia in ocorrencias:
            conflitos = (
                ReservaRecurso.objects.filter(
                    objeto=objeto,
                    data=ocorrencia.data,
                    status=ReservaRecurso.Status.DEFERIDA,
                    hora_inicio__lt=hora_fim,
                    hora_fim__gt=hora_inicio,
                )
                .exclude(serie_id=instance.serie_id)
            )
            if conflitos.exists():
                raise ValidationError(self.conflict_error_message)

    def clean(self):
        """Executa as validações de recorrência, horários e conflitos deferidos."""

        cleaned = super().clean()
        objeto = cleaned.get("objeto")
        data = cleaned.get("data")
        hora_inicio = cleaned.get("hora_inicio")
        hora_fim = cleaned.get("hora_fim")
        recorrencia = cleaned.get("recorrencia") or ""
        recorrencia_fim = cleaned.get("recorrencia_fim")
        responsavel = (cleaned.get("responsavel") or "").strip()
        cleaned["responsavel"] = responsavel or self.get_responsavel_padrao()
        self.usuario_responsavel_resolvido = self._resolver_usuario_por_nome(cleaned["responsavel"])

        if self.instance and self.instance.pk and recorrencia:
            self.add_error("recorrencia", "A recorrência só pode ser definida na criação.")

        if self.modo_fiscal and not responsavel:
            self.add_error("responsavel", "Informe o nome do responsável.")

        if recorrencia and not recorrencia_fim:
            self.add_error("recorrencia_fim", "Informe a data fim para usar recorrência.")
        if recorrencia and data and recorrencia_fim and recorrencia_fim < data:
            self.add_error("recorrencia_fim", "A data fim deve ser maior ou igual à data inicial.")

        if hora_inicio and hora_fim and hora_fim <= hora_inicio:
            self.add_error("hora_fim", "A hora final deve ser maior que a hora inicial.")

        if self.instance and self.instance.pk and not self.instance.pode_editar_solicitante and not self.modo_fiscal:
            raise ValidationError("Esta solicitação não pode mais ser alterada pelo solicitante.")

        if objeto and data and hora_inicio and hora_fim:
            dates = self.get_recurrence_dates() or [data]
            for occ_date in dates:
                conflitos = (
                    ReservaRecurso.objects.filter(
                        objeto=objeto,
                        data=occ_date,
                        status=ReservaRecurso.Status.DEFERIDA,
                        hora_inicio__lt=hora_fim,
                        hora_fim__gt=hora_inicio,
                    )
                    .exclude(pk=self.instance.pk)
                )
                if self.instance and self.instance.serie_id:
                    conflitos = conflitos.exclude(serie_id=self.instance.serie_id)
                if conflitos.exists():
                    self.add_error(None, self.conflict_error_message)
                    return cleaned

        # Mesmo se alguém tentar alterar o valor manualmente via POST, o backend mantém
        # o responsável como o próprio usuário no fluxo comum.
        if self.request_user and getattr(self.request_user, "is_authenticated", False) and not self.modo_fiscal:
            cleaned["responsavel"] = self.get_responsavel_padrao()

        return cleaned


class ReservaRecursoAnaliseForm(BootstrapModelForm):
    """Formulário do fiscal para deferir ou indeferir a solicitação."""

    decisao = forms.ChoiceField(
        label="Decisão",
        choices=[("DEFERIR", "Deferir"), ("INDEFERIR", "Indeferir")],
    )

    class Meta:
        model = ReservaRecurso
        fields = ["justificativa_indeferimento"]
        widgets = {"justificativa_indeferimento": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        cleaned = super().clean()
        decisao = cleaned.get("decisao")
        justificativa = (cleaned.get("justificativa_indeferimento") or "").strip()
        if decisao == "INDEFERIR" and not justificativa:
            self.add_error("justificativa_indeferimento", "Informe a justificativa do indeferimento.")
        return cleaned
