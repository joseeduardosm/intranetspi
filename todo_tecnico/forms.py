# Criado por OpenAI Codex em 19/06/2026
# Objetivo: Preparar formulários Bootstrap do backlog técnico simplificado.

from django import forms
from django.utils import timezone

from .models import CodexConfiguracao, TarefaTecnica


BOOTSTRAP_INPUT = "form-control form-control-lg"


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes padrão do portal aos campos visíveis do formulário."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = "form-select form-select-lg"
            elif isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                css = "form-control"
            else:
                css = BOOTSTRAP_INPUT
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css}".strip()


class TarefaTecnicaCadastroForm(BootstrapModelForm):
    """Usa apenas os campos de abertura e edição da tarefa, sem expor a solução antes da hora."""

    class Meta:
        model = TarefaTecnica
        fields = ["titulo", "descricao"]
        widgets = {
            "titulo": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: Ajustar validação do módulo de contratos",
                }
            ),
            "descricao": forms.Textarea(
                attrs={
                    "placeholder": "Descreva a pendência técnica, o problema observado e o objetivo esperado.",
                    "rows": 5,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["titulo"].required = False
        self.fields["titulo"].help_text = "Opcional. Use quando quiser dar um nome curto para a tarefa."
        self.fields["descricao"].help_text = "Obrigatória. Explique a demanda com o máximo de contexto útil."


class TarefaTecnicaSolucaoForm(BootstrapModelForm):
    """Expõe apenas o campo de solução na etapa de encerramento da tarefa."""

    class Meta:
        model = TarefaTecnica
        fields = ["solucao"]
        widgets = {
            "solucao": forms.Textarea(
                attrs={
                    "placeholder": "Descreva a solução adotada para encerrar a tarefa.",
                    "rows": 6,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["solucao"].required = True
        self.fields["solucao"].help_text = "Obrigatória para concluir a tarefa."


class TarefaTecnicaEdicaoConcluidaForm(BootstrapModelForm):
    """Permite revisar o conteúdo completo da tarefa já concluída, inclusive a solução."""

    class Meta:
        model = TarefaTecnica
        fields = ["titulo", "descricao", "solucao"]
        widgets = {
            "titulo": forms.TextInput(
                attrs={
                    "placeholder": "Ex.: Ajustar validação do módulo de contratos",
                }
            ),
            "descricao": forms.Textarea(
                attrs={
                    "placeholder": "Descreva a pendência técnica, o problema observado e o objetivo esperado.",
                    "rows": 5,
                }
            ),
            "solucao": forms.Textarea(
                attrs={
                    "placeholder": "Descreva a solução aplicada para manter o histórico completo.",
                    "rows": 6,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["titulo"].required = False
        self.fields["titulo"].help_text = "Opcional. Use quando quiser dar um nome curto para a tarefa."
        self.fields["descricao"].help_text = "Obrigatória. Explique a demanda com o máximo de contexto útil."
        self.fields["solucao"].required = False
        self.fields["solucao"].help_text = "Edite a solução quando precisar complementar o histórico da tarefa concluída."


class CodexAgendamentoForm(forms.Form):
    """Recebe a data e hora desejadas para inserir uma tarefa na fila futura do Codex."""

    agendado_para = forms.DateTimeField(
        label="Iniciar em",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": BOOTSTRAP_INPUT}),
    )

    def clean_agendado_para(self):
        agendado_para = self.cleaned_data["agendado_para"]
        if timezone.is_naive(agendado_para):
            agendado_para = timezone.make_aware(agendado_para, timezone.get_current_timezone())
        if agendado_para <= timezone.now():
            raise forms.ValidationError("Informe uma data futura para o agendamento do Codex.")
        return agendado_para


class CodexConfiguracaoForm(BootstrapModelForm):
    """Permite ajustar o executor sem espalhar parâmetros fixos pelo código."""

    class Meta:
        model = CodexConfiguracao
        fields = [
            "codex_path",
            "codex_home",
            "workspace_path",
            "modelo",
            "sandbox",
            "habilitar_busca_web",
            "timeout_minutos",
            "limite_tokens_5h",
            "limite_tokens_semanal",
            "nome_servico",
            "instrucoes_fixas",
        ]
        widgets = {
            "instrucoes_fixas": forms.Textarea(
                attrs={
                    "rows": 8,
                    "placeholder": "Regras fixas reaproveitadas em toda execução automática do Codex.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codex_path"].help_text = "Ex.: /root/.local/bin/codex"
        self.fields["codex_home"].help_text = "Diretório onde o Codex mantém autenticação e estado local."
        self.fields["workspace_path"].help_text = "Raiz do projeto que o Codex deve abrir ao executar a tarefa."
        self.fields["modelo"].help_text = "Modelo padrão usado nas execuções não interativas."
        self.fields["timeout_minutos"].help_text = "Tempo máximo que uma execução pode ficar rodando antes de ser marcada com erro."
        self.fields["limite_tokens_5h"].help_text = "Usado pelo painel para calcular o consumo local das últimas cinco horas."
        self.fields["limite_tokens_semanal"].help_text = "Usado pelo painel para calcular o consumo local dos últimos sete dias."
