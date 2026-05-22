from django.contrib import admin

from .models import NavbarItem


@admin.register(NavbarItem)
class NavbarItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'parent', 'url', 'ordem', 'ativo', 'abrir_nova_aba')
    list_filter = ('ativo', 'abrir_nova_aba', 'parent')
    search_fields = ('titulo', 'url')
    ordering = ('ordem', 'titulo')
