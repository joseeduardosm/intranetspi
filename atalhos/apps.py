# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Configurar o app de atalhos no Django.

from django.apps import AppConfig


class AtalhosConfig(AppConfig):
    """Define a configuração básica do app de gerenciamento de atalhos."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'atalhos'
