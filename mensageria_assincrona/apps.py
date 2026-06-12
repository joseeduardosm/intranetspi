# Criado por OpenAI Codex em 12/06/2026
# Configura o app de mensageria e expõe metadados usados pela navegação ACL.

from django.apps import AppConfig


class MensageriaAssincronaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mensageria_assincrona"
    verbose_name = "Mensageria"
    acl_url_base = "/mensageria/"

