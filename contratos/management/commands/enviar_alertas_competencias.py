from django.core.management.base import BaseCommand

from contratos.services import enviar_alertas_monitoramento_competencias


class Command(BaseCommand):
    help = 'Dispara alertas automáticos das competências em monitoramento.'

    def handle(self, *args, **options):
        enviados = enviar_alertas_monitoramento_competencias()
        self.stdout.write(self.style.SUCCESS(f'Alerta(s) enviados: {enviados}'))
