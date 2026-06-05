# Criado por José Eduardo Santana Martins em 04/06/2026
# Declara a configuração do app setores para registro no projeto Django.
from django.apps import AppConfig


class SetoresConfig(AppConfig):
    """Configuração principal do app de setores."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'setores'
