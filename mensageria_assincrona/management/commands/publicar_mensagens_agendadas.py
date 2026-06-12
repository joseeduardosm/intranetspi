# Criado por OpenAI Codex em 12/06/2026
# Publica mensagens agendadas cujo horário de entrega já foi alcançado.

from django.core.management.base import BaseCommand

from mensageria_assincrona.services import publicar_agendadas_pendentes


class Command(BaseCommand):
    help = "Publica mensagens agendadas com publicar_em menor ou igual ao horário atual."

    def handle(self, *args, **options):
        total = publicar_agendadas_pendentes()
        self.stdout.write(self.style.SUCCESS(f"{total} mensagem(ns) publicada(s)."))

