# Criado por OpenAI Codex em 12/06/2026
# Injeta no template base o estado global da caixa de entrada e do modal bloqueante.

from __future__ import annotations

from django.db import OperationalError, ProgrammingError

from .services import indicadores_pendencias_usuario, listar_pendentes_usuario


def mensageria_global(request):
    """Entrega ao template base apenas o necessário para topbar e modal."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "mensageria_pendentes_count": 0,
            "mensageria_primeira_pendente": None,
            "mensageria_modal_modo": "",
            "mensageria_modal_skip": False,
        }

    try:
        indicadores = indicadores_pendencias_usuario(user)
        primeira = None
        if indicadores["primeira_pendente_id"]:
            primeira = listar_pendentes_usuario(user).first()
    except (OperationalError, ProgrammingError):
        # Durante deploys ou antes das migrações do app, a base ainda pode não ter
        # as tabelas da mensageria. Nessa janela, a topbar deve continuar funcional.
        return {
            "mensageria_pendentes_count": 0,
            "mensageria_primeira_pendente": None,
            "mensageria_modal_modo": "",
            "mensageria_modal_skip": False,
        }

    resolver_match = getattr(request, "resolver_match", None)
    on_inbox = bool(
        resolver_match
        and getattr(resolver_match, "namespace", "") == "mensageria"
        and getattr(resolver_match, "url_name", "") in {"minhas", "minha_detail"}
    )

    return {
        "mensageria_pendentes_count": indicadores["pendentes_count"],
        "mensageria_primeira_pendente": primeira,
        "mensageria_modal_modo": indicadores["modal_modo"],
        "mensageria_modal_skip": on_inbox and indicadores["modal_modo"] == "consolidado",
    }
