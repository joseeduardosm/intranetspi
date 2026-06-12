# Criado por OpenAI Codex em 12/06/2026
# Centraliza as regras de publicação, pendência e auditoria do módulo.

from __future__ import annotations

import json
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from setores.models import UserSetorMembership

from .models import Mensagem, MensagemDestino, MensagemEvento


User = get_user_model()


def _serializar_payload_email(payload):
    """Aceita texto ou JSON e normaliza para um dicionário serializável."""

    if payload in (None, "", {}):
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        texto = payload.strip()
        if not texto:
            return {}
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            return {"texto": texto}
    return {"valor": payload}


def registrar_evento(mensagem, tipo_acao, usuario=None, payload=None):
    """Grava trilha mínima de auditoria de forma padronizada."""

    return MensagemEvento.objects.create(
        mensagem=mensagem,
        usuario=usuario,
        tipo_acao=tipo_acao,
        payload=payload or {},
    )


def criar_mensagem_rascunho(*, assunto, corpo, prioridade=Mensagem.Prioridade.NORMAL, criada_por=None, expira_em=None, payload_email=None):
    """Cria a mensagem principal sem gerar destinos até a publicação."""

    mensagem = Mensagem.objects.create(
        assunto=assunto,
        corpo=corpo,
        prioridade=prioridade,
        criada_por=criada_por,
        expira_em=expira_em,
        payload_email=_serializar_payload_email(payload_email),
        status_envio=Mensagem.StatusEnvio.RASCUNHO,
    )
    registrar_evento(mensagem, MensagemEvento.TipoAcao.CRIACAO, usuario=criada_por)
    return mensagem


def _destinatarios_publicacao(mensagem: Mensagem) -> list[User]:
    """Consolida usuários diretos e oriundos de setores sem duplicidade."""

    users_by_id = {}
    for usuario in mensagem.usuarios_alvo.filter(is_active=True):
        users_by_id[usuario.pk] = usuario

    memberships = UserSetorMembership.objects.filter(
        setor__in=mensagem.setores_alvo.all(),
        user__is_active=True,
    ).select_related("user")
    for membership in memberships:
        users_by_id[membership.user_id] = membership.user
    return list(users_by_id.values())


@transaction.atomic
def publicar_mensagem(mensagem: Mensagem, usuario=None, publicada_em=None):
    """Publica a mensagem de forma idempotente e cria os destinos efetivos."""

    agora = publicada_em or timezone.now()
    mensagem = Mensagem.objects.select_for_update().get(pk=mensagem.pk)

    if mensagem.status_envio == Mensagem.StatusEnvio.CANCELADA:
        raise ValueError("Mensagens canceladas não podem ser publicadas.")

    if mensagem.status_envio == Mensagem.StatusEnvio.PUBLICADA:
        return mensagem

    destinatarios = _destinatarios_publicacao(mensagem)
    novos_destinos = []
    for destino_user in destinatarios:
        destino, created = MensagemDestino.objects.get_or_create(
            mensagem=mensagem,
            usuario=destino_user,
            defaults={
                "status_destinatario": MensagemDestino.StatusDestinatario.PENDENTE,
                "entregue_em": agora,
                "assunto_snapshot": mensagem.assunto,
                "corpo_snapshot": mensagem.corpo,
            },
        )
        if created:
            novos_destinos.append(destino.pk)

    mensagem.status_envio = Mensagem.StatusEnvio.PUBLICADA
    mensagem.publicada_em = agora
    mensagem.publicar_em = None
    mensagem.save(update_fields=["status_envio", "publicada_em", "publicar_em", "updated_at"])
    registrar_evento(
        mensagem,
        MensagemEvento.TipoAcao.PUBLICACAO,
        usuario=usuario,
        payload={"destinos_criados": len(novos_destinos)},
    )
    return mensagem


@transaction.atomic
def agendar_mensagem(mensagem: Mensagem, publicar_em, usuario=None):
    """Marca a mensagem para publicação futura sem gerar destinos antecipadamente."""

    mensagem = Mensagem.objects.select_for_update().get(pk=mensagem.pk)
    if not mensagem.pode_editar:
        raise ValueError("A mensagem não pode mais ser agendada.")
    mensagem.status_envio = Mensagem.StatusEnvio.AGENDADA
    mensagem.publicar_em = publicar_em
    mensagem.publicada_em = None
    mensagem.save(update_fields=["status_envio", "publicar_em", "publicada_em", "updated_at"])
    registrar_evento(
        mensagem,
        MensagemEvento.TipoAcao.AGENDAMENTO,
        usuario=usuario,
        payload={"publicar_em": publicar_em.isoformat()},
    )
    return mensagem


@transaction.atomic
def cancelar_mensagem(mensagem: Mensagem, usuario=None):
    """Cancela rascunhos ou agendamentos e trava futuras alterações."""

    mensagem = Mensagem.objects.select_for_update().get(pk=mensagem.pk)
    if mensagem.status_envio == Mensagem.StatusEnvio.PUBLICADA:
        raise ValueError("Mensagens publicadas não podem ser canceladas.")
    mensagem.status_envio = Mensagem.StatusEnvio.CANCELADA
    mensagem.publicar_em = None
    mensagem.save(update_fields=["status_envio", "publicar_em", "updated_at"])
    registrar_evento(mensagem, MensagemEvento.TipoAcao.CANCELAMENTO, usuario=usuario)
    return mensagem


def _query_pendentes_usuario(user):
    """Retorna a base comum das consultas de pendências válidas do usuário."""

    agora = timezone.now()
    return (
        MensagemDestino.objects.filter(
            usuario=user,
            status_destinatario=MensagemDestino.StatusDestinatario.PENDENTE,
            mensagem__status_envio=Mensagem.StatusEnvio.PUBLICADA,
        )
        .filter(Q(mensagem__expira_em__isnull=True) | Q(mensagem__expira_em__gt=agora))
        .select_related("mensagem")
        .order_by("entregue_em", "id")
    )


def listar_pendentes_usuario(user):
    """Lista todas as mensagens ainda aguardando ciência do usuário."""

    if not user or not user.is_authenticated:
        return MensagemDestino.objects.none()
    return _query_pendentes_usuario(user)


def obter_primeira_pendente_usuario(user):
    """Resolve a primeira pendência ativa para o modal global."""

    if not user or not user.is_authenticated:
        return None
    return _query_pendentes_usuario(user).first()


@transaction.atomic
def marcar_visualizacao(destino: MensagemDestino, user):
    """Registra apenas a primeira abertura para auditoria sem gerar ciência implícita."""

    destino = MensagemDestino.objects.select_for_update().select_related("mensagem").get(pk=destino.pk)
    if destino.usuario_id != user.pk:
        raise PermissionError("Você só pode visualizar suas próprias mensagens.")
    if destino.visualizada_em:
        return destino
    destino.visualizada_em = timezone.now()
    destino.save(update_fields=["visualizada_em", "updated_at"])
    registrar_evento(
        destino.mensagem,
        MensagemEvento.TipoAcao.VISUALIZACAO,
        usuario=user,
        payload={"destino_id": destino.pk},
    )
    return destino


@transaction.atomic
def marcar_ciente(destino: MensagemDestino, user):
    """Confirma a ciência individual do destinatário e preserva a rastreabilidade."""

    destino = MensagemDestino.objects.select_for_update().select_related("mensagem").get(pk=destino.pk)
    if destino.usuario_id != user.pk:
        raise PermissionError("Você só pode confirmar ciência das suas próprias mensagens.")
    if destino.status_destinatario == MensagemDestino.StatusDestinatario.CIENTE:
        return destino

    agora = timezone.now()
    if not destino.visualizada_em:
        destino.visualizada_em = agora
    destino.status_destinatario = MensagemDestino.StatusDestinatario.CIENTE
    destino.ciente_em = agora
    destino.save(update_fields=["status_destinatario", "visualizada_em", "ciente_em", "updated_at"])
    registrar_evento(
        destino.mensagem,
        MensagemEvento.TipoAcao.CIENCIA,
        usuario=user,
        payload={"destino_id": destino.pk},
    )
    return destino


def indicadores_pendencias_usuario(user):
    """Produz o payload leve usado por topbar, modal e endpoint interno."""

    pendentes = listar_pendentes_usuario(user)
    primeira = pendentes.first()
    total = pendentes.count()
    return {
        "pendentes_count": total,
        "primeira_pendente_id": primeira.pk if primeira else None,
        "modal_modo": "consolidado" if total > 3 else ("individual" if total else ""),
    }


def mensagens_admin_queryset():
    """Anota totais de destinos e ciências para a listagem administrativa."""

    return Mensagem.objects.annotate(
        destinos_total=Count("destinos", distinct=True),
        destinos_cientes=Count(
            "destinos",
            filter=Q(destinos__status_destinatario=MensagemDestino.StatusDestinatario.CIENTE),
            distinct=True,
        ),
    ).prefetch_related("usuarios_alvo", "setores_alvo").order_by("-created_at", "-id")


def publicar_agendadas_pendentes():
    """Publica lote de mensagens agendadas cujo horário já chegou."""

    agora = timezone.now()
    mensagens = list(
        Mensagem.objects.filter(
            status_envio=Mensagem.StatusEnvio.AGENDADA,
            publicar_em__lte=agora,
        ).order_by("publicar_em", "id")
    )
    publicadas = 0
    for mensagem in mensagens:
        publicar_mensagem(mensagem, publicada_em=agora)
        publicadas += 1
    return publicadas
