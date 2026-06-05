from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .models import RegraAcesso, Recurso
from usuarios.services import SYSTEM_USERNAMES

User = get_user_model()

class RegraAcessoForm(forms.ModelForm):
    class Meta:
        model = RegraAcesso
        fields = ['recurso', 'nivel', 'usuario', 'grupo']
        widgets = {
            'recurso': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'nivel': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'usuario': forms.Select(attrs={'class': 'form-select'}),
            'grupo': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra usuários humanos ativos
        self.fields['usuario'].queryset = User.objects.filter(is_active=True).exclude(
            username__in=SYSTEM_USERNAMES
        ).order_by('first_name', 'username')
        self.fields['grupo'].queryset = Group.objects.all().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        usuario = cleaned_data.get('usuario')
        grupo = cleaned_data.get('grupo')

        if not usuario and not grupo:
            raise forms.ValidationError("Você deve selecionar pelo menos um Usuário ou um Grupo/Setor.")

        return cleaned_data
