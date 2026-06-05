# Criado por José Eduardo Santana Martins em 04/06/2026
# Registra o app usuarios e carrega sinais de criação automática de perfil.
from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    """Configuração principal do app de usuários."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "usuarios"
    verbose_name = "Usuarios"

    def ready(self):
        # Importa sinais no momento correto do ciclo de inicialização do Django.
        from . import signals  # noqa: F401
