# Criado por José Eduardo Santana Martins em 04/06/2026

from django.contrib import admin
from .models import Recurso, RegraAcesso


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    """Exibe e localiza os módulos protegidos cadastrados como recursos de ACL."""

    list_display = ("nome", "slug", "descricao")
    search_fields = ("nome", "slug", "descricao")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(RegraAcesso)
class RegraAcessoAdmin(admin.ModelAdmin):
    """Administra as regras que vinculam nível de acesso a usuários ou grupos."""

    list_display = ("id", "recurso", "nivel", "usuario", "grupo", "criado_em")
    list_filter = ("nivel", "recurso", "grupo")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "grupo__name", "recurso__nome")

    def get_queryset(self, request):
        # Carrega relações usadas na listagem do admin para evitar consultas repetidas.
        return super().get_queryset(request).select_related("recurso", "usuario", "grupo")
