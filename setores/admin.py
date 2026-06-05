# Criado por José Eduardo Santana Martins em 04/06/2026
# Configura a administração dos setores e dos vínculos entre usuários e setores.
from django.contrib import admin

from .models import SetorNode, UserSetorMembership


@admin.register(SetorNode)
class SetorNodeAdmin(admin.ModelAdmin):
    """Facilita busca e edição da árvore de setores no Django Admin."""

    list_display = ('id', 'group', 'parent', 'lider', 'ativo')
    search_fields = ('group__name', 'parent__group__name', 'lider__username', 'lider__first_name')
    autocomplete_fields = ('parent', 'lider')


@admin.register(UserSetorMembership)
class UserSetorMembershipAdmin(admin.ModelAdmin):
    """Permite auditar e ajustar vínculos de usuários com setores."""

    list_display = ('id', 'user', 'setor', 'criado_em')
    search_fields = ('user__username', 'user__first_name', 'setor__group__name')
    autocomplete_fields = ('user', 'setor')
