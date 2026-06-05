# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Configurar o app de geração de assinatura de e-mail no Django.

from django.apps import AppConfig


class AssinaturaEEmailConfig(AppConfig):
    """Define a configuração básica do app de assinatura de e-mail."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assinatura_e_mail'
