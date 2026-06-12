# Criado por OpenAI Codex em 12/06/2026
# Configura o app de reserva de carros e expõe a URL base para navegação ACL.

from django.apps import AppConfig


class ReservaCarrosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reserva_carros"
    verbose_name = "Reserva de Carros"
    acl_url_base = "/reserva-carros/"

