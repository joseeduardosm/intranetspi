"""Configuração principal do app de reserva de garagem."""

from django.apps import AppConfig


class ReservaGaragemConfig(AppConfig):
    """Expõe metadados do módulo e a URL base usada pelo ACL."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "reserva_garagem"
    verbose_name = "Reserva de Garagem"
    acl_url_base = "/reserva-garagem/"
