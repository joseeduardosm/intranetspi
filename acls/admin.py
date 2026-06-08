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

    list_display = ("id", "recurso", "nivel", "listar_usuarios", "listar_grupos", "criado_em")
    list_filter = ("nivel", "recurso", "grupos")
    search_fields = ("usuarios__username", "usuarios__first_name", "usuarios__last_name", "grupos__name", "recurso__nome")

    def get_queryset(self, request):
        # Carrega relações usadas na listagem do admin para evitar consultas repetidas.
        return super().get_queryset(request).select_related("recurso").prefetch_related("usuarios", "grupos")

    @admin.display(description="Usuários")
    def listar_usuarios(self, obj):
        # Exibe um resumo curto para manter a grade do admin legível.
        return ", ".join(
            usuario.get_full_name() or usuario.username
            for usuario in obj.usuarios.all()[:3]
        ) or "-"

    @admin.display(description="Grupos/Setores")
    def listar_grupos(self, obj):
        # Exibe um resumo curto para manter a grade do admin legível.
        return ", ".join(grupo.name for grupo in obj.grupos.all()[:3]) or "-"
