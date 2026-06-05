# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Registrar itens da navbar no admin do Django com filtros de gestão.

from django.contrib import admin

from .models import NavbarItem


@admin.register(NavbarItem)
class NavbarItemAdmin(admin.ModelAdmin):
    """Configura a listagem administrativa dos itens de menu."""

    list_display = ('id', 'titulo', 'parent', 'url', 'ordem', 'ativo', 'abrir_nova_aba')
    list_filter = ('ativo', 'abrir_nova_aba', 'parent')
    search_fields = ('titulo', 'url')
    ordering = ('ordem', 'titulo')
