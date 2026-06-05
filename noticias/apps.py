# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Configurar o app de notícias no Django.

from django.apps import AppConfig


class NoticiasConfig(AppConfig):
    """Define a configuração básica do app de notícias."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'noticias'
    verbose_name = 'Noticias'
