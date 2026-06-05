# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Criar automaticamente o ciclo inicial após cadastro de imóvel.

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Imovel
from .services import create_initial_cycle


@receiver(post_save, sender=Imovel)
def create_imovel_initial_cycle(sender, instance, created, **kwargs):
    """Garante que todo imóvel novo comece com um ciclo processual inicial."""

    if created:
        create_initial_cycle(instance)
