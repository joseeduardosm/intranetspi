# Criado por OpenAI Codex em 19/06/2026
# Objetivo: Exibir tarefas técnicas no admin com colunas úteis para suporte interno.

from django.contrib import admin

from .models import TarefaTecnica


@admin.register(TarefaTecnica)
class TarefaTecnicaAdmin(admin.ModelAdmin):
    """Facilita inspeção administrativa do backlog técnico no Django admin."""

    list_display = ("titulo", "criado_por", "criado_em", "concluido_em")
    list_filter = ("concluido_em", "criado_por")
    search_fields = ("titulo", "criado_por__username", "criado_por__first_name", "criado_por__last_name")
