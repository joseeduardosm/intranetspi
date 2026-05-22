from django import forms

from .models import NavbarItem


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


class NavbarItemForm(BootstrapModelForm):
    class Meta:
        model = NavbarItem
        fields = ['titulo', 'url', 'parent', 'ordem', 'ativo', 'abrir_nova_aba']
        help_texts = {
            'url': 'Opcional para menus dropdown. Use caminhos internos como /noticias/ ou links externos como https://exemplo.com.',
            'parent': 'Opcional. Escolha um item pai para criar submenu.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = NavbarItem.objects.filter(parent__isnull=True).order_by('ordem', 'titulo')
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields['parent'].queryset = queryset
        self.fields['parent'].required = False
        self.fields['url'].required = False

    def clean_url(self):
        return (self.cleaned_data.get('url') or '').strip()
