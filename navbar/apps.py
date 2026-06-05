# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Configurar o app de navbar no Django.

from django.apps import AppConfig


class NavbarConfig(AppConfig):
    """Define a configuração básica do app da barra de navegação."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'navbar'
    verbose_name = 'Navbar'
