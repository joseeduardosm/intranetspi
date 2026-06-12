# Criado por OpenAI Codex em 12/06/2026
# Reúne os formulários do app de mensageria com seleção múltipla de usuários e setores.

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

from setores.models import SetorNode
from usuarios.services import visible_users_queryset

from .models import Mensagem


User = get_user_model()

BOOTSTRAP_INPUT = "form-control form-control-lg"
BOOTSTRAP_TEXTAREA = "form-control"


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes Bootstrap sem obrigar cada formulário a repetir widgets."""

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
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css}".strip()


class MensagemForm(BootstrapModelForm):
    """Concentra conteúdo, audiência e intenção de publicação do painel administrativo."""

    class ModoPublicacao(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Salvar como rascunho"
        IMEDIATA = "IMEDIATA", "Publicar imediatamente"
        AGENDADA = "AGENDADA", "Agendar publicação"

    modo_publicacao = forms.ChoiceField(
        label="Opção de publicação",
        choices=ModoPublicacao.choices,
    )

    class Meta:
        model = Mensagem
        fields = [
            "assunto",
            "corpo",
            "prioridade",
            "usuarios_alvo",
            "setores_alvo",
            "expira_em",
            "publicar_em",
            "payload_email",
        ]
        widgets = {
            "corpo": forms.Textarea(attrs={"rows": 10}),
            "usuarios_alvo": forms.SelectMultiple(attrs={"size": 12}),
            "setores_alvo": forms.SelectMultiple(attrs={"size": 10}),
            "expira_em": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "publicar_em": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "payload_email": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuarios_alvo"].queryset = visible_users_queryset().order_by("first_name", "username")
        self.fields["setores_alvo"].queryset = SetorNode.objects.select_related("group").filter(ativo=True).order_by(
            "group__name", "id"
        )
        self.fields["usuarios_alvo"].label = "Usuários"
        self.fields["setores_alvo"].label = "Setores"
        self.fields["expira_em"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["publicar_em"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["payload_email"].required = False
        self.fields["payload_email"].help_text = "Estrutura opcional reservada para a futura integração com e-mail."

        if self.instance and self.instance.pk:
            if self.instance.status_envio == Mensagem.StatusEnvio.AGENDADA:
                self.initial["modo_publicacao"] = self.ModoPublicacao.AGENDADA
            elif self.instance.status_envio == Mensagem.StatusEnvio.PUBLICADA:
                self.initial["modo_publicacao"] = self.ModoPublicacao.IMEDIATA
            else:
                self.initial["modo_publicacao"] = self.ModoPublicacao.RASCUNHO
        else:
            self.initial["modo_publicacao"] = self.ModoPublicacao.RASCUNHO

        # Após a publicação ou cancelamento, o form serve só para visualização.
        if self.instance and self.instance.pk and not self.instance.pode_editar:
            for field in self.fields.values():
                field.disabled = True
            self.fields["modo_publicacao"].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        usuarios = cleaned_data.get("usuarios_alvo")
        setores = cleaned_data.get("setores_alvo")
        modo = cleaned_data.get("modo_publicacao")
        publicar_em = cleaned_data.get("publicar_em")
        expira_em = cleaned_data.get("expira_em")

        if (not usuarios or not usuarios.exists()) and (not setores or not setores.exists()):
            raise forms.ValidationError("Selecione ao menos um usuário ou um setor para a audiência.")

        if modo == self.ModoPublicacao.AGENDADA and not publicar_em:
            self.add_error("publicar_em", "Informe a data e hora da publicação agendada.")

        if publicar_em and publicar_em <= timezone.now() and modo == self.ModoPublicacao.AGENDADA:
            self.add_error("publicar_em", "A publicação agendada deve estar no futuro.")

        if publicar_em and expira_em and expira_em <= publicar_em:
            self.add_error("expira_em", "A expiração deve ocorrer depois da publicação.")

        return cleaned_data
