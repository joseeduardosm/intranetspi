# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Preparar formulários Bootstrap para cadastro e edição de atalhos.

from django import forms

from .models import Atalho


# Classe padrão aplicada aos campos textuais do formulário.
BOOTSTRAP_INPUT = 'form-control form-control-lg'


class BootstrapModelForm(forms.ModelForm):
    """Adiciona classes Bootstrap aos widgets conforme o tipo de campo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Checkboxes e selects precisam de classes próprias para manter o visual correto.
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                css = 'form-select form-select-lg'
            else:
                css = BOOTSTRAP_INPUT
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {css}'.strip()


class AtalhoForm(BootstrapModelForm):
    """Formulário principal para configurar imagem, destino, ordem e status do atalho."""

    class Meta:
        model = Atalho
        fields = ['titulo', 'imagem', 'url', 'ordem', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Textos de ajuda orientam o formato aceito sem alterar a validação do modelo.
        self.fields['imagem'].help_text = 'Obrigatoria. Aceita PNG, JPG ou JPEG.'
        self.fields['url'].help_text = 'Use um caminho interno como /licitacoes/ ou uma URL externa com http:// ou https://.'
