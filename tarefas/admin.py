# Criado por OpenAI Codex em 23/06/2026
# Registra os modelos do módulo de tarefas para apoio administrativo e auditoria.

from django.contrib import admin

from .models import Tarefa, TarefaHistorico


@admin.register(Tarefa)
class TarefaAdmin(admin.ModelAdmin):
    """Expõe os campos principais da tarefa no admin."""

    list_display = ("id", "titulo", "status", "criado_por", "responsavel", "prioridade", "prazo", "criado_em")
    list_filter = ("status", "prioridade", "criado_em")
    search_fields = (
        "titulo",
        "descricao",
        "criado_por__username",
        "criado_por__perfil__nome_completo",
        "responsavel__username",
        "responsavel__perfil__nome_completo",
    )
    autocomplete_fields = ("criado_por", "responsavel")


@admin.register(TarefaHistorico)
class TarefaHistoricoAdmin(admin.ModelAdmin):
    """Exibe o histórico cronológico da tarefa para consulta de suporte."""

    list_display = ("id", "tarefa", "tipo_evento", "autor", "titulo_evento", "criado_em")
    list_filter = ("tipo_evento", "criado_em")
    search_fields = ("titulo_evento", "descricao_evento", "comentario", "nome_arquivo", "tarefa__titulo")
    autocomplete_fields = ("tarefa", "autor")
