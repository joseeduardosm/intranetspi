# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Expor a aplicação ASGI usada por servidores assíncronos compatíveis.

"""
ASGI config for aplicacoesspi project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Define o módulo de configurações usado quando o servidor ASGI inicializa o Django.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aplicacoesspi.settings')

application = get_asgi_application()
