from __future__ import annotations

from django import forms
from django.contrib.auth.models import Group
from django.db import transaction

from .models import SetorNode
from .services import (
    group_name_exists,
    primary_setor_for_user,
    sync_user_memberships_for_setor,
    user_display_name,
    visible_users_queryset,
)


BOOTSTRAP_INPUT = 'form-control form-control-lg'


class UsuarioSetorChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return user_display_name(obj)


class SetorForm(forms.ModelForm):
    nome = forms.CharField(label='Nome do grupo', max_length=150, widget=forms.TextInput(attrs={'class': BOOTSTRAP_INPUT}))
    usuarios = UsuarioSetorChoiceField(
        label='Usuários pertencentes ao setor',
        required=False,
        queryset=visible_users_queryset(),
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': 10}),
    )

    class Meta:
        model = SetorNode
        fields = ['nome', 'parent', 'lider', 'ativo']
        widgets = {
            'parent': forms.Select(attrs={'class': 'form-select form-select-lg'}),
            'lider': forms.Select(attrs={'class': 'form-select form-select-lg'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lider'].queryset = visible_users_queryset()
        self.fields['parent'].queryset = SetorNode.objects.select_related('group').order_by('group__name')
        self.fields['ativo'].widget.attrs['class'] = 'form-check-input'
        if self.instance and self.instance.pk:
            self.fields['nome'].initial = self.instance.group.name
            self.fields['usuarios'].initial = self.instance.memberships.values_list('user_id', flat=True)
            self.fields['parent'].queryset = self.fields['parent'].queryset.exclude(pk=self.instance.pk)

    def clean_nome(self):
        nome = (self.cleaned_data.get('nome') or '').strip()
        exclude_id = self.instance.group_id if self.instance and self.instance.pk else None
        if group_name_exists(nome, exclude_group_id=exclude_id):
            raise forms.ValidationError('Já existe um grupo com este nome.')
        return nome

    def _post_clean(self):
        nome = (self.data.get('nome') or '').strip()
        if not self.instance.group_id and nome:
            self.instance.group = Group(name=nome)
        super()._post_clean()

    @transaction.atomic
    def save(self, commit=True):
        setor = super().save(commit=False)
        nome = self.cleaned_data['nome']
        old_name = ''
        if self.instance and self.instance.pk:
            group = self.instance.group
            old_name = group.name
            if group.name != nome:
                group.name = nome
                group.save(update_fields=['name'])
        else:
            group = Group.objects.create(name=nome)
            setor.group = group

        if commit:
            setor.save()
            self.save_m2m()
            selected_users = list(self.cleaned_data.get('usuarios') or [])
            sync_user_memberships_for_setor(setor, selected_users)
            if old_name and old_name != nome:
                from usuarios.models import UsuarioPerfil
                UsuarioPerfil.objects.filter(setor=old_name).update(setor=nome)
            for user in selected_users:
                perfil = getattr(user, 'perfil', None)
                if perfil and not perfil.setor:
                    perfil.setor = setor.group.name
                    perfil.save(update_fields=['setor', 'atualizado_em'])
        return setor


class SetorUserChoiceField(forms.ChoiceField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.widget.attrs['class'] = 'form-select form-select-lg'


def setor_usuario_choices(instance=None):
    choices = [('', 'Selecione um setor')]
    setores = list(SetorNode.objects.select_related('group').filter(ativo=True).order_by('group__name'))
    current = primary_setor_for_user(instance.user) if instance and getattr(instance, 'user_id', None) else None
    if current and all(setor.pk != current.pk for setor in setores):
        setores.append(current)
    choices.extend((str(setor.pk), setor.group.name) for setor in setores)
    return choices
