# Criado por OpenAI Codex em 12/06/2026
# Define os formulários da frota, configuração e solicitações de viagem.

from __future__ import annotations

from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.utils import timezone

from usuarios.services import visible_users_queryset
from setores.services import user_display_name

from .models import Carro, ConfiguracaoReservaCarros, Motorista, ReservaCarro


User = get_user_model()

BOOTSTRAP_INPUT = "form-control form-control-lg"
BOOTSTRAP_TEXTAREA = "form-control"


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes Bootstrap consistentes com o restante do portal."""

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


class CarroForm(BootstrapModelForm):
    """CRUD da frota usada na etapa de deferimento."""

    class Meta:
        model = Carro
        fields = ["marca", "modelo", "placa", "cor", "ativo"]
        widgets = {
            "cor": forms.TextInput(attrs={"type": "color", "class": "form-control form-control-color"}),
        }


class MotoristaForm(BootstrapModelForm):
    """CRUD do cadastro de motoristas próprios do módulo."""

    class Meta:
        model = Motorista
        fields = ["nome_completo", "contato", "ativo"]


class ConfiguracaoReservaCarrosForm(BootstrapModelForm):
    """Permite definir o grupo operacional de fiscais do módulo."""

    class Meta:
        model = ConfiguracaoReservaCarros
        fields = ["grupo_fiscais"]
        widgets = {
            "grupo_fiscais": forms.Select(attrs={"class": "form-select form-select-lg"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["grupo_fiscais"].queryset = Group.objects.order_by("name")
        self.fields["grupo_fiscais"].required = False
        self.fields["grupo_fiscais"].help_text = "Usuários desse grupo poderão deferir e indeferir as solicitações."


class ReservaCarroSolicitacaoForm(BootstrapModelForm):
    """Formulário usado pelo solicitante para abrir ou ajustar a viagem."""

    passageiros = forms.ModelMultipleChoiceField(
        label="Pessoas que viajarão",
        queryset=User.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 12}),
    )

    class Meta:
        model = ReservaCarro
        fields = [
            "saida_planejada_em",
            "retorno_planejado_em",
            "destino_endereco",
            "modo_destino",
            "motivo_viagem",
            "observacoes_solicitante",
        ]
        widgets = {
            "saida_planejada_em": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "retorno_planejado_em": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "motivo_viagem": forms.Textarea(attrs={"rows": 5}),
            "observacoes_solicitante": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop("request_user", None)
        super().__init__(*args, **kwargs)
        self.fields["passageiros"].queryset = visible_users_queryset().order_by("first_name", "username")
        self.fields["passageiros"].label_from_instance = user_display_name
        self.fields["saida_planejada_em"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["retorno_planejado_em"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["modo_destino"].help_text = "Indique se o veículo deve permanecer aguardando no destino."
        if self.instance and self.instance.pk:
            self.initial["passageiros"] = self.instance.passageiros_vinculos.values_list("usuario_id", flat=True)

    def clean(self):
        cleaned = super().clean()
        saida = cleaned.get("saida_planejada_em")
        retorno = cleaned.get("retorno_planejado_em")
        agora = timezone.now()

        if saida and timezone.is_naive(saida):
            saida = timezone.make_aware(saida, timezone.get_current_timezone())
            cleaned["saida_planejada_em"] = saida
        if retorno and timezone.is_naive(retorno):
            retorno = timezone.make_aware(retorno, timezone.get_current_timezone())
            cleaned["retorno_planejado_em"] = retorno

        if saida and retorno and saida >= retorno:
            self.add_error("retorno_planejado_em", "O retorno planejado deve ocorrer depois da saída.")

        if saida:
            if saida < agora + timedelta(days=2):
                self.add_error("saida_planejada_em", "A saída precisa ser solicitada com pelo menos 2 dias de antecedência.")
            if saida > agora + timedelta(days=30):
                self.add_error("saida_planejada_em", "A saída não pode ultrapassar 30 dias a partir da solicitação.")
            if timezone.localtime(saida).weekday() >= 5:
                self.add_error("saida_planejada_em", "A saída não pode iniciar no fim de semana.")

        if self.instance and self.instance.pk and not self.instance.pode_editar_solicitante:
            raise forms.ValidationError("Esta solicitação não pode mais ser alterada pelo solicitante.")

        return cleaned


class ReservaCarroAnaliseForm(BootstrapModelForm):
    """Formulário do fiscal para deferir ou indeferir a solicitação."""

    decisao = forms.ChoiceField(
        label="Decisão",
        choices=[
            ("DEFERIR", "Deferir"),
            ("INDEFERIR", "Indeferir"),
        ],
    )

    class Meta:
        model = ReservaCarro
        fields = [
            "justificativa_indeferimento",
            "deslocamento_ida_minutos",
            "deslocamento_retorno_minutos",
            "carro",
            "motorista",
        ]
        widgets = {
            "justificativa_indeferimento": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["carro"].queryset = Carro.objects.filter(ativo=True).order_by("marca", "modelo", "placa")
        self.fields["motorista"].queryset = Motorista.objects.filter(ativo=True).order_by("nome_completo")
        self.fields["justificativa_indeferimento"].required = False
        for field_name in ["deslocamento_ida_minutos", "deslocamento_retorno_minutos", "carro", "motorista"]:
            self.fields[field_name].required = False

    def clean(self):
        cleaned = super().clean()
        decisao = cleaned.get("decisao")
        justificativa = (cleaned.get("justificativa_indeferimento") or "").strip()
        deslocamento_ida = cleaned.get("deslocamento_ida_minutos")
        deslocamento_retorno = cleaned.get("deslocamento_retorno_minutos")
        carro = cleaned.get("carro")
        motorista = cleaned.get("motorista")

        if decisao == "INDEFERIR":
            if not justificativa:
                self.add_error("justificativa_indeferimento", "Informe a justificativa do indeferimento.")
        elif decisao == "DEFERIR":
            if deslocamento_ida is None:
                self.add_error("deslocamento_ida_minutos", "Informe o deslocamento de ida.")
            if deslocamento_retorno is None:
                self.add_error("deslocamento_retorno_minutos", "Informe o deslocamento de retorno.")
            if not carro:
                self.add_error("carro", "Selecione o carro da viagem.")
            if not motorista:
                self.add_error("motorista", "Selecione o motorista.")

        return cleaned
