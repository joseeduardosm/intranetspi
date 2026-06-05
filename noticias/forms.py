# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Preparar o formulário Bootstrap de cadastro e edição de notícias.

from django import forms
from .models import Noticia


# Classes visuais padrão dos campos do formulário editorial.
BOOTSTRAP_INPUT = 'form-control form-control-lg'
BOOTSTRAP_TEXTAREA = 'form-control spi-textarea-compact'


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes Bootstrap aos widgets conforme o tipo de campo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Textareas ficam compactas para facilitar edição de textos longos.
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                css = 'form-select form-select-lg'
            elif isinstance(field.widget, forms.Textarea):
                css = BOOTSTRAP_TEXTAREA
            else:
                css = BOOTSTRAP_INPUT
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {css}'.strip()


class NoticiaForm(BootstrapModelForm):
    """Formulário principal para dados editoriais, imagem, anexo e agendamento."""

    class Meta:
        model = Noticia
        fields = ['imagem_destaque', 'anexo_pdf', 'titulo', 'texto_noticia', 'data_publicacao', 'status', 'fixada']
        widgets = {
            'texto_noticia': forms.Textarea(attrs={'rows': 14}),
            'data_publicacao': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # O input datetime-local precisa de formato compatível com o navegador.
        self.fields['data_publicacao'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['anexo_pdf'].label = 'Anexo'
        self.fields['anexo_pdf'].help_text = 'Opcional. PDFs serão exibidos na postagem; outros arquivos ficarão disponíveis para download.'
