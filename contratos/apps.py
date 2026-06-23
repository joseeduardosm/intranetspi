# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Registrar o módulo simplificado de contratos V2.

from django.apps import AppConfig


class ContratosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contratos'
    verbose_name = 'Contratos V2'

    def ready(self):
        """Carrega os sinais de auditoria quando o app sobe."""

        from . import signals  # noqa: F401
