# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Configurar o módulo de contratos administrativos dentro do portal.

from django.apps import AppConfig


class ContratosConfig(AppConfig):
    """Configuração principal do app de gestão de contratos administrativos."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'contratos'
    verbose_name = 'Contratos'

