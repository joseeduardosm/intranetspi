from django.apps import AppConfig


class ReservaEspacosConfig(AppConfig):
    """Configuração principal do módulo de reserva de espaços."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "reserva_espacos"
    # O label antigo é preservado para manter compatibilidade com a migração
    # inicial já aplicada no banco antes da renomeação do pacote.
    label = "reservas_recursos"
    verbose_name = "Reserva de Espaços"
