from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Imovel
from .services import create_initial_cycle


@receiver(post_save, sender=Imovel)
def create_imovel_initial_cycle(sender, instance, created, **kwargs):
    if created:
        create_initial_cycle(instance)
