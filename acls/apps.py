from django.apps import AppConfig

class AclsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'acls'
    verbose_name = 'Controle de Acesso (ACL)'

    def ready(self):
        import acls.signals
