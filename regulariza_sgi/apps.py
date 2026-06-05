# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Configurar o app Regulariza SGI e carregar seus sinais.

from django.apps import AppConfig


class RegularizaSgiConfig(AppConfig):
    """Configura o app e ativa os sinais de criação automática de ciclos."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'regulariza_sgi'

    def ready(self):
        # Importa sinais no carregamento do app para criar ciclo inicial após cadastro de imóvel.
        from . import signals  # noqa: F401
