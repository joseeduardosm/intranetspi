# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Preparar o formulário Bootstrap de criação e edição dos itens da navbar.

from django import forms

from .models import NavbarItem


# Classe padrão para campos textuais do formulário.
BOOTSTRAP_INPUT = 'form-control form-control-lg'


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes Bootstrap aos widgets conforme o tipo de campo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Checkboxes e selects precisam de classes específicas para manter o visual correto.
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
    """Formulário usado para configurar links, submenus, ordem e status da navbar."""

    class Meta:
        model = NavbarItem
        fields = ['titulo', 'url', 'parent', 'ordem', 'ativo', 'abrir_nova_aba']
        help_texts = {
            'url': 'Opcional para menus dropdown. Use caminhos internos como /noticias/ ou links externos como https://exemplo.com.',
            'parent': 'Opcional. Escolha um item pai para criar submenu.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Só itens raiz podem ser pais, evitando submenus com mais de um nível.
        queryset = NavbarItem.objects.filter(parent__isnull=True).order_by('ordem', 'titulo')
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields['parent'].queryset = queryset
        self.fields['parent'].required = False
        self.fields['url'].required = False

    def clean_url(self):
        """Normaliza URLs vazias para permitir itens que funcionam apenas como dropdown."""

        return (self.cleaned_data.get('url') or '').strip()
