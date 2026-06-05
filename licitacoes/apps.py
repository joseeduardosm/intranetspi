# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Configurar o app de licitações no Django.

from django.apps import AppConfig


class LicitacoesConfig(AppConfig):
    """Define a configuração básica do app de licitações."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'licitacoes'
