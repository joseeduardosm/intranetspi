# Criado por OpenAI Codex em 23/06/2026
# Reúne os formulários Bootstrap do módulo de tarefas em Django puro.

from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model

from usuarios.models import UsuarioPerfil
from usuarios.services import visible_users_queryset

from .models import Tarefa, TarefaHistorico


User = get_user_model()
BOOTSTRAP_INPUT = "form-control form-control-lg"


def user_display_name(usuario):
    """Padroniza a exibição de usuários pelos nomes humanos do portal."""

    perfil = getattr(usuario, "perfil", None)
    nome = getattr(perfil, "nome_completo", "") if perfil else ""
    return (nome or usuario.get_full_name() or usuario.username).strip()


class UsuarioNomeChoiceField(forms.ModelChoiceField):
    """Garante que qualquer seletor de usuário no módulo mostre nome em vez de login."""

    def label_from_instance(self, obj):
        return user_display_name(obj)


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes padrão do portal aos campos visíveis."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select form-select-lg"
            elif isinstance(field.widget, forms.Textarea):
                css = "form-control"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            else:
                css = BOOTSTRAP_INPUT
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css}".strip()


class SuperiorImediatoForm(BootstrapModelForm):
    """Recebe o superior imediato obrigatório para liberar o módulo."""

    superior_imediato = UsuarioNomeChoiceField(
        label="Superior imediato",
        queryset=User.objects.none(),
        widget=forms.Select(),
    )

    class Meta:
        model = UsuarioPerfil
        fields = ["superior_imediato"]

    def __init__(self, *args, current_user=None, **kwargs):
        self.current_user = current_user
        super().__init__(*args, **kwargs)
        self.fields["superior_imediato"].queryset = (
            visible_users_queryset()
            .select_related("perfil")
            .exclude(pk=self.instance.user_id)
            .order_by("perfil__nome_completo", "first_name", "username")
        )
        self.fields["superior_imediato"].help_text = "Selecione quem é o seu superior imediato para liberar o uso do módulo."


class TarefaForm(BootstrapModelForm):
    """Formulário principal de criação e edição da tarefa."""

    class Meta:
        model = Tarefa
        fields = ["titulo", "descricao", "prazo", "prioridade"]
        widgets = {
            "titulo": forms.TextInput(attrs={"placeholder": "Ex.: Preparar minuta do despacho"}),
            "descricao": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Descreva a tarefa com contexto suficiente para consulta futura."}
            ),
            "prazo": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["titulo"].help_text = "Obrigatório. Use um título curto e objetivo."
        self.fields["descricao"].help_text = "Obrigatória. Registre o contexto principal da tarefa."
        self.fields["prazo"].help_text = "Obrigatório. O prazo poderá ser alterado depois com justificativa."


class TarefaPrazoForm(BootstrapModelForm):
    """Formulário específico para mudança de prazo com justificativa obrigatória."""

    justificativa = forms.CharField(
        label="Justificativa",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Explique o motivo da alteração do prazo."}),
    )

    class Meta:
        model = Tarefa
        fields = ["prazo"]
        widgets = {
            "prazo": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["prazo"].help_text = "Informe o novo prazo da tarefa."
        self.fields["justificativa"].help_text = "Obrigatória para registrar o histórico da alteração."


class TarefaHistoricoForm(BootstrapModelForm):
    """Adiciona comentários, anexos ou ambos na linha do tempo da tarefa."""

    class Meta:
        model = TarefaHistorico
        fields = ["comentario", "arquivo"]
        widgets = {
            "comentario": forms.Textarea(
                attrs={"rows": 4, "placeholder": "Digite um comentário para o histórico da tarefa."}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["comentario"].required = False
        self.fields["arquivo"].required = False
        self.fields["arquivo"].help_text = "Opcional. Você pode anexar um arquivo e/ou registrar um comentário."

    def clean(self):
        cleaned_data = super().clean()
        comentario = (cleaned_data.get("comentario") or "").strip()
        arquivo = cleaned_data.get("arquivo")
        if not comentario and not arquivo:
            raise forms.ValidationError("Informe um comentário, anexe um arquivo ou ambos.")
        return cleaned_data


class TarefaBuscaForm(forms.Form):
    """Concentra filtros simples da visão macro do usuário."""

    q = forms.CharField(required=False, label="Busca")
    prioridade = forms.ChoiceField(
        required=False,
        label="Prioridade",
        choices=[("", "Todas")] + list(Tarefa.Prioridade.choices),
        widget=forms.Select(attrs={"class": "form-select form-select-lg"}),
    )
    status = forms.ChoiceField(
        required=False,
        label="Status",
        choices=[("", "Todos")] + list(Tarefa.Status.choices),
        widget=forms.Select(attrs={"class": "form-select form-select-lg"}),
    )


class TarefaHistoricoBuscaForm(forms.Form):
    """Filtra o histórico da tarefa sem sair da página de detalhe."""

    q = forms.CharField(required=False, label="Pesquisar no histórico")
    tipo = forms.ChoiceField(
        required=False,
        label="Tipo",
        choices=[
            ("", "Tudo"),
            ("COMENTARIOS", "Comentários"),
            ("ALTERACOES", "Alterações"),
            ("SISTEMA", "Sistema"),
            ("ANEXOS", "Anexos"),
        ],
        widget=forms.Select(attrs={"class": "form-select form-select-lg"}),
    )
