# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Centralizar consultas de notícias públicas e publicação de agendadas.

from django.utils import timezone

from .models import Noticia


def noticias_publicadas():
    """Retorna notícias publicadas cuja data já está vencida para exibição pública."""

    return Noticia.objects.filter(
        status=Noticia.Status.PUBLICADA,
        data_publicacao__lte=timezone.now(),
    ).order_by('-fixada', '-data_publicacao', '-id')


def publicar_noticias_agendadas():
    """Publica notícias agendadas cuja data de publicação já chegou."""

    return Noticia.objects.filter(
        status=Noticia.Status.AGENDADA,
        data_publicacao__lte=timezone.now(),
    ).update(status=Noticia.Status.PUBLICADA)
