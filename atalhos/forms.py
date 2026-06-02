from django import forms

from .models import Atalho


BOOTSTRAP_INPUT = 'form-control form-control-lg'


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
    class Meta:
        model = Atalho
        fields = ['titulo', 'imagem', 'url', 'ordem', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['imagem'].help_text = 'Obrigatoria. Aceita PNG, JPG ou JPEG.'
        self.fields['url'].help_text = 'Use um caminho interno como /licitacoes/ ou uma URL externa com http:// ou https://.'

