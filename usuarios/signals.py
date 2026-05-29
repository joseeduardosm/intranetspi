from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UsuarioPerfil


User = get_user_model()


@receiver(post_save, sender=User)
def ensure_usuario_perfil(sender, instance, created, **kwargs):
    if created:
        UsuarioPerfil.objects.get_or_create(user=instance)

