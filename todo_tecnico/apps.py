# Criado por OpenAI Codex em 19/06/2026
# Objetivo: Configurar o app de backlog técnico simplificado para cadastro automático na ACL.

from django.apps import AppConfig


class TodoTecnicoConfig(AppConfig):
    """Define a configuração base do módulo de tarefas técnicas."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "todo_tecnico"
    verbose_name = "To-Do Técnico"
    acl_url_base = "/todo-tecnico/"
