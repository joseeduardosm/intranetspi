# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir itens da navbar, submenus de um nível e regras de link externo.

from django.core.exceptions import ValidationError
from django.db import models


class NavbarItem(models.Model):
    """Representa um item de menu principal ou submenu da barra de navegação."""

    titulo = models.CharField('Titulo', max_length=120)
    url = models.CharField('URL', max_length=500, blank=True)
    parent = models.ForeignKey(
        'self',
        verbose_name='Item pai',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='filhos',
    )
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    abrir_nova_aba = models.BooleanField('Abrir em nova aba', default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'titulo', 'id']
        verbose_name = 'Item da navbar'
        verbose_name_plural = 'Itens da navbar'

    def __str__(self):
        return self.titulo

    def clean(self):
        super().clean()
        # A navbar aceita apenas menu principal e um nível de submenu para manter a UI simples.
        if self.parent_id and self.parent and self.parent.parent_id:
            raise ValidationError({'parent': 'Use apenas um nivel de submenu.'})
        if self.pk and self.parent_id == self.pk:
            raise ValidationError({'parent': 'Um item nao pode ser pai dele mesmo.'})

    @property
    def is_external(self):
        """Identifica links que devem ser tratados como externos."""

        return (self.url or '').startswith(('http://', 'https://', '//'))

    @property
    def target_blank(self):
        """Abre em nova aba quando marcado ou quando o link é externo."""

        return self.abrir_nova_aba or self.is_external
