# Criado por José Eduardo Santana Martins em 04/06/2026
# Garante a criação automática de perfil sempre que um usuário Django é criado.
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UsuarioPerfil


User = get_user_model()


@receiver(post_save, sender=User)
def ensure_usuario_perfil(sender, instance, created, **kwargs):
    """Cria UsuarioPerfil no primeiro salvamento do User."""

    if created:
        UsuarioPerfil.objects.get_or_create(user=instance)
