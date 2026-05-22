from django.utils import timezone

from .models import Noticia


def noticias_publicadas():
    return Noticia.objects.filter(
        status=Noticia.Status.PUBLICADA,
        data_publicacao__lte=timezone.now(),
    ).order_by('-fixada', '-data_publicacao', '-id')


def publicar_noticias_agendadas():
    return Noticia.objects.filter(
        status=Noticia.Status.AGENDADA,
        data_publicacao__lte=timezone.now(),
    ).update(status=Noticia.Status.PUBLICADA)
