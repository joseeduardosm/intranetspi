from django.core.management.base import BaseCommand

from noticias.services import publicar_noticias_agendadas


class Command(BaseCommand):
    help = 'Publica noticias agendadas cuja data de publicacao ja venceu.'

    def handle(self, *args, **options):
        count = publicar_noticias_agendadas()
        self.stdout.write(self.style.SUCCESS(f'{count} noticia(s) publicada(s).'))
