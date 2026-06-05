# Criado por José Eduardo Santana Martins em 04/06/2026

from django.apps import AppConfig


class AclsConfig(AppConfig):
    """Configura o app de ACL e ativa a sincronização automática de recursos."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'acls'
    verbose_name = 'Controle de Acesso (ACL)'

    def ready(self):
        # Importa os sinais quando o Django inicializa o app para manter recursos locais sincronizados.
        import acls.signals
