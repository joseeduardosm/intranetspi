# Criado por OpenAI Codex em 20/06/2026
# Objetivo: Processar em background a fila de execuções automáticas do Codex do To-Do Técnico.

from django.core.management.base import BaseCommand

from todo_tecnico.services import executar_fila_codex


class Command(BaseCommand):
    """Mantém um único worker responsável por consumir a fila e respeitar agendamentos."""

    help = "Processa a fila de execuções do Codex do módulo To-Do Técnico."

    def handle(self, *args, **options):
        total = executar_fila_codex()
        self.stdout.write(self.style.SUCCESS(f"Execuções processadas: {total}"))
