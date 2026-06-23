# Criado por OpenAI Codex em 23/06/2026
# Configura o app de tarefas para cadastro automático na ACL do portal.

from django.apps import AppConfig


class TarefasConfig(AppConfig):
    """Define os metadados principais do app de tarefas."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "tarefas"
    verbose_name = "Tarefas"
    acl_url_base = "/tarefas/"
