# Criado por José Eduardo Santana Martins em 04/06/2026
# Define a estrutura hierárquica dos setores e os vínculos entre usuários
# e grupos utilizados pelo módulo.
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models


class SetorNode(models.Model):
    """Representa um setor como nó de árvore ligado a um grupo do Django."""

    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='setor_node')
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='children',
    )
    lider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='setores_liderados',
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['group__name', 'id']
        verbose_name = 'Setor'
        verbose_name_plural = 'Setores'

    def __str__(self):
        return self.group.name

    def clean(self):
        super().clean()
        if self.id is not None and self.parent_id == self.id:
            raise ValidationError({'parent': 'Um setor não pode ser pai dele mesmo.'})

        # Percorre os ancestrais para impedir ciclos que quebrariam o organograma.
        visited = set()
        cursor = self.parent
        while cursor:
            if cursor.id in visited or (self.id and cursor.id == self.id):
                raise ValidationError({'parent': 'Ciclo detectado na árvore de setores.'})
            visited.add(cursor.id)
            cursor = cursor.parent

    @property
    def nome(self):
        return self.group.name

    @property
    def grupo_pai_nome(self):
        return self.parent.group.name if self.parent_id else ''


class UserSetorMembership(models.Model):
    """Registra a participação de um usuário em um setor específico."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='setor_memberships',
    )
    setor = models.ForeignKey(
        SetorNode,
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('user', 'setor')]
        ordering = ['user__username', 'setor__group__name', 'id']
        verbose_name = 'Vínculo de usuário ao setor'
        verbose_name_plural = 'Vínculos de usuários aos setores'

    def __str__(self):
        return f'{self.user} - {self.setor}'
