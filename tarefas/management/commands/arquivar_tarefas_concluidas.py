# Criado por OpenAI Codex em 23/06/2026
# Arquiva automaticamente tarefas concluídas há mais de 3 dias de forma idempotente.

from django.core.management.base import BaseCommand

from tarefas.services import arquivar_tarefas_concluidas


class Command(BaseCommand):
    help = "Arquiva automaticamente tarefas concluídas há mais de 3 dias."

    def handle(self, *args, **options):
        total = arquivar_tarefas_concluidas()
        self.stdout.write(self.style.SUCCESS(f"{total} tarefa(s) arquivada(s) automaticamente."))
