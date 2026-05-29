from django import forms
from .models import Noticia


BOOTSTRAP_INPUT = 'form-control form-control-lg'
BOOTSTRAP_TEXTAREA = 'form-control spi-textarea-compact'


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    class Meta:
        model = Noticia
        fields = ['imagem_destaque', 'anexo_pdf', 'titulo', 'texto_noticia', 'data_publicacao', 'status', 'fixada']
        widgets = {
            'texto_noticia': forms.Textarea(attrs={'rows': 14}),
            'data_publicacao': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_publicacao'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['anexo_pdf'].label = 'Anexo'
        self.fields['anexo_pdf'].help_text = 'Opcional. PDFs serão exibidos na postagem; outros arquivos ficarão disponíveis para download.'
