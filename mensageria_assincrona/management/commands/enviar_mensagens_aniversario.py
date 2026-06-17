# Criado por OpenAI Codex em 15/06/2026
# Dispara as mensagens automáticas de aniversário para os usuários que fazem aniversário no dia.

from django.core.management.base import BaseCommand
from django.utils import timezone

from mensageria_assincrona.services import enviar_mensagens_automaticas_aniversario


class Command(BaseCommand):
    help = "Publica mensagens internas de aniversário para os aniversariantes do dia."

    def handle(self, *args, **options):
        referencia = timezone.localdate()
        total = enviar_mensagens_automaticas_aniversario(referencia=referencia)
        self.stdout.write(
            self.style.SUCCESS(
                f"{total} mensagem(ns) de aniversário enviada(s) para {referencia:%d/%m/%Y}."
            )
        )
