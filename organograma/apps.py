# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Configurar o app de organograma no Django.

from django.apps import AppConfig


class OrganogramaConfig(AppConfig):
    """Define a configuração básica do app de organograma."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'organograma'
