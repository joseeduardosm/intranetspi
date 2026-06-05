# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Publicar via comando as notícias agendadas cuja data já venceu.

from django.core.management.base import BaseCommand

from noticias.services import publicar_noticias_agendadas


class Command(BaseCommand):
    """Comando usado por rotina manual ou agendada para publicar notícias vencidas."""

    help = 'Publica noticias agendadas cuja data de publicacao ja venceu.'

    def handle(self, *args, **options):
        # O serviço retorna a quantidade de registros atualizados para feedback no terminal.
        count = publicar_noticias_agendadas()
        self.stdout.write(self.style.SUCCESS(f'{count} noticia(s) publicada(s).'))
