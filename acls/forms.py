# Criado por José Eduardo Santana Martins em 04/06/2026

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import RegraAcesso, Recurso
from usuarios.services import SYSTEM_USERNAMES

User = get_user_model()


class RegraAcessoForm(forms.ModelForm):
    """Formulário usado para criar e editar regras de acesso no painel de ACL."""

    class Meta:
        model = RegraAcesso
        fields = ['recurso', 'nivel', 'usuarios', 'grupos']
        widgets = {
            'recurso': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'nivel': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            # O select múltiplo original permanece oculto no template para o Django
            # continuar recebendo um campo padrão, enquanto a interface usa um picker.
            'usuarios': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
            'grupos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limita a seleção a usuários humanos ativos e grupos cadastrados no sistema.
        self.fields['usuarios'].queryset = User.objects.filter(is_active=True).exclude(
            username__in=SYSTEM_USERNAMES
        ).order_by('first_name', 'username')
        self.fields['grupos'].queryset = Group.objects.all().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        usuarios = cleaned_data.get('usuarios')
        grupos = cleaned_data.get('grupos')

        # A regra precisa apontar para pelo menos um alvo para ter efeito no controle de acesso.
        if (not usuarios or not usuarios.exists()) and (not grupos or not grupos.exists()):
            raise forms.ValidationError("Você deve selecionar pelo menos um Usuário ou um Grupo/Setor.")

        return cleaned_data
