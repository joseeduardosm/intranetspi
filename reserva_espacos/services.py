"""Centraliza regras operacionais, conflitos e notificações do módulo."""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone

from mensageria_assincrona.services import criar_mensagem_rascunho, publicar_mensagem

from .models import ConfiguracaoReservaEspacos, ObjetoReservavel, ReservaRecurso, ReservaRecursoEvento


def registrar_evento(reserva, acao, usuario=None, payload=None):
    """Grava a trilha mínima de auditoria da reserva de salas."""

    return ReservaRecursoEvento.objects.create(
        reserva=reserva,
        usuario=usuario,
        acao=acao,
        payload=payload or {},
    )


def fiscal_group():
    """Obtém o grupo operacional configurado para os fiscais do módulo."""

    return ConfiguracaoReservaEspacos.singleton().grupo_fiscais


def user_is_fiscal(user) -> bool:
    """Identifica se o usuário participa do fluxo fiscal deste módulo."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    group = fiscal_group()
    return bool(group and user.groups.filter(pk=group.pk).exists())


def _format_date(value):
    """Formata datas no padrão brasileiro para mensagens e histórico."""

    if not value:
        return "-"
    return value.strftime("%d/%m/%Y")


def _format_time(value):
    """Formata horários no padrão do portal para mensagens e detalhes."""

    if not value:
        return "-"
    return value.strftime("%H:%M")


def _serie_queryset(reserva: ReservaRecurso):
    """Retorna a série completa quando houver, ou apenas a própria ocorrência."""

    if reserva.serie_id:
        return ReservaRecurso.objects.filter(serie_id=reserva.serie_id).order_by("data", "hora_inicio", "id")
    return ReservaRecurso.objects.filter(pk=reserva.pk)


def _cancel_scope_queryset(
    reserva: ReservaRecurso,
    *,
    apply_scope: str = "single",
    data_inicial: date | None = None,
    data_final: date | None = None,
):
    """Resolve quais ocorrências da reserva serão canceladas conforme o escopo solicitado."""

    if not reserva.serie_id or apply_scope == "single":
        return ReservaRecurso.objects.filter(pk=reserva.pk).order_by("data", "hora_inicio", "id")
    if apply_scope == "all":
        return ReservaRecurso.objects.filter(serie_id=reserva.serie_id).order_by("data", "hora_inicio", "id")
    if apply_scope == "range":
        if not (data_inicial and data_final):
            raise ValidationError("Informe a data inicial e a data final do cancelamento.")
        if data_final < data_inicial:
            raise ValidationError("A data final do cancelamento deve ser maior ou igual à data inicial.")
        queryset = ReservaRecurso.objects.filter(
            serie_id=reserva.serie_id,
            data__range=(data_inicial, data_final),
        ).order_by("data", "hora_inicio", "id")
        if not queryset.exists():
            raise ValidationError("Nenhuma ocorrência da série foi encontrada no período informado para cancelamento.")
        return queryset
    raise ValidationError("Escopo de cancelamento inválido.")


def _datas_serie_display(reservas):
    """Resume o intervalo da série em texto para notificação."""

    datas = list(reservas.values_list("data", flat=True))
    if not datas:
        return "-"
    return f"{_format_date(datas[0])} a {_format_date(datas[-1])}" if len(datas) > 1 else _format_date(datas[0])


def _scope_display(apply_scope: str, data_inicial: date | None = None, data_final: date | None = None) -> str:
    """Traduz o escopo técnico em texto humano para mensagens e histórico."""

    if apply_scope == "all":
        return "Toda a série"
    if apply_scope == "range" and data_inicial and data_final:
        return f"Período de {_format_date(data_inicial)} a {_format_date(data_final)}"
    return "Somente esta ocorrência"


def _mensagem_nova_solicitacao_para_fiscais(reservas):
    """Monta a mensagem enviada ao grupo fiscal quando nasce uma nova solicitação."""

    reserva = reservas.first()
    intervalo = _datas_serie_display(reservas)
    link_analise = reverse("reserva_espacos:fila_fiscal_analise", args=[reserva.pk])
    assunto = f"Nova solicitação de reserva de sala #{reserva.pk}"
    corpo = (
        "Uma nova solicitação de reserva de sala aguarda análise fiscal.\n\n"
        f"Solicitante: {reserva.responsavel}\n"
        f"Objeto: {reserva.objeto.nome_exibicao}\n"
        f"Período: {intervalo}\n"
        f"Horário: {_format_time(reserva.hora_inicio)} às {_format_time(reserva.hora_fim)}\n"
        f"Título: {reserva.titulo}\n"
        f"Observações: {reserva.observacoes or '-'}\n\n"
        f"Analisar solicitação: {link_analise}"
    )
    payload = {
        "tipo": "nova_solicitacao_reserva_espaco",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "status": reserva.status,
        "objeto": reserva.objeto.nome_exibicao,
        "link_analise": link_analise,
        "datas": [data.isoformat() for data in reservas.values_list("data", flat=True)],
    }
    return assunto, corpo, payload


def _mensagem_reserva_deferida(reservas):
    """Monta assunto, corpo e payload para a notificação de deferimento."""

    reserva = reservas.first()
    intervalo = _datas_serie_display(reservas)
    assunto = f"Reserva de sala deferida #{reserva.pk}"
    corpo = (
        "Sua solicitação de reserva de sala foi deferida.\n\n"
        f"Objeto: {reserva.objeto.nome_exibicao}\n"
        f"Período: {intervalo}\n"
        f"Horário: {_format_time(reserva.hora_inicio)} às {_format_time(reserva.hora_fim)}\n"
        f"Título: {reserva.titulo}\n"
        f"Observações: {reserva.observacoes or '-'}"
    )
    payload = {
        "tipo": "deferimento_reserva_espaco",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "objeto": reserva.objeto.nome_exibicao,
        "status": reserva.status,
        "datas": [data.isoformat() for data in reservas.values_list("data", flat=True)],
    }
    return assunto, corpo, payload


def _mensagem_reserva_indeferida(reservas):
    """Monta a notificação textual do indeferimento."""

    reserva = reservas.first()
    intervalo = _datas_serie_display(reservas)
    assunto = f"Reserva de sala indeferida #{reserva.pk}"
    corpo = (
        "Sua solicitação de reserva de sala foi indeferida.\n\n"
        f"Objeto: {reserva.objeto.nome_exibicao}\n"
        f"Período: {intervalo}\n"
        f"Horário: {_format_time(reserva.hora_inicio)} às {_format_time(reserva.hora_fim)}\n"
        f"Título: {reserva.titulo}\n"
        f"Justificativa: {reserva.justificativa_indeferimento}"
    )
    payload = {
        "tipo": "indeferimento_reserva_espaco",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "objeto": reserva.objeto.nome_exibicao,
        "status": reserva.status,
        "justificativa": reserva.justificativa_indeferimento,
        "datas": [data.isoformat() for data in reservas.values_list("data", flat=True)],
    }
    return assunto, corpo, payload


def _mensagem_reserva_cancelada(reservas, usuario_cancelamento, *, motivo: str, apply_scope: str, data_inicial=None, data_final=None):
    """Monta a mensagem enviada ao solicitante quando a reserva é cancelada."""

    reserva = reservas.first()
    intervalo = _datas_serie_display(reservas)
    nome_cancelador = (
        getattr(getattr(usuario_cancelamento, "perfil", None), "nome_completo", "")
        or usuario_cancelamento.get_full_name()
        or usuario_cancelamento.username
    )
    cancelamento_administrativo = reserva.criado_por_id != getattr(usuario_cancelamento, "id", None)
    origem_texto = "cancelada administrativamente" if cancelamento_administrativo else "cancelada"
    escopo = _scope_display(apply_scope, data_inicial, data_final)
    assunto = f"Reserva de sala cancelada #{reserva.pk}"
    corpo = (
        f"Sua reserva de sala foi {origem_texto}.\n\n"
        f"Objeto: {reserva.objeto.nome_exibicao}\n"
        f"Período: {intervalo}\n"
        f"Horário: {_format_time(reserva.hora_inicio)} às {_format_time(reserva.hora_fim)}\n"
        f"Escopo do cancelamento: {escopo}\n"
        f"Cancelada por: {nome_cancelador}\n"
        f"Motivo do cancelamento: {motivo}\n"
        f"Título: {reserva.titulo}\n"
        f"Observações: {reserva.observacoes or '-'}"
    )
    payload = {
        "tipo": "cancelamento_reserva_espaco",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "objeto": reserva.objeto.nome_exibicao,
        "status": reserva.status,
        "cancelada_por": nome_cancelador,
        "motivo_cancelamento": motivo,
        "apply_scope": apply_scope,
        "data_inicial": data_inicial.isoformat() if data_inicial else "",
        "data_final": data_final.isoformat() if data_final else "",
        "origem": "fluxo_fiscal" if cancelamento_administrativo else "fluxo_usuario",
        "datas": [data.isoformat() for data in reservas.values_list("data", flat=True)],
    }
    return assunto, corpo, payload


def notificar_solicitante(reservas, usuario_responsavel=None):
    """Cria e publica a mensagem assíncrona após decisão fiscal."""

    reserva = reservas.first()
    if reserva.status == ReservaRecurso.Status.DEFERIDA:
        assunto, corpo, payload = _mensagem_reserva_deferida(reservas)
    elif reserva.status == ReservaRecurso.Status.INDEFERIDA:
        assunto, corpo, payload = _mensagem_reserva_indeferida(reservas)
    else:
        return None

    mensagem = criar_mensagem_rascunho(
        assunto=assunto,
        corpo=corpo,
        criada_por=usuario_responsavel,
        payload_email=payload,
    )
    if reserva.criado_por:
        mensagem.usuarios_alvo.add(reserva.criado_por)
    publicar_mensagem(mensagem, usuario=usuario_responsavel)
    return mensagem


def notificar_fiscais_nova_solicitacao(reservas, usuario_responsavel=None):
    """Publica uma mensagem para todos os usuários do grupo fiscal com link direto de análise."""

    group = fiscal_group()
    if not group:
        return None

    usuarios_fiscais = list(group.user_set.filter(is_active=True).distinct())
    if not usuarios_fiscais:
        return None

    assunto, corpo, payload = _mensagem_nova_solicitacao_para_fiscais(reservas)
    mensagem = criar_mensagem_rascunho(
        assunto=assunto,
        corpo=corpo,
        criada_por=usuario_responsavel,
        payload_email=payload,
    )
    mensagem.usuarios_alvo.add(*usuarios_fiscais)
    publicar_mensagem(mensagem, usuario=usuario_responsavel)
    return mensagem


def notificar_cancelamento(reservas, usuario_responsavel=None, *, motivo: str, apply_scope: str, data_inicial=None, data_final=None):
    """Publica uma mensagem ao solicitante quando a reserva é cancelada."""

    reserva = reservas.first()
    if not reserva or reserva.status != ReservaRecurso.Status.CANCELADA:
        return None
    if not reserva.criado_por:
        return None

    assunto, corpo, payload = _mensagem_reserva_cancelada(
        reservas,
        usuario_responsavel,
        motivo=motivo,
        apply_scope=apply_scope,
        data_inicial=data_inicial,
        data_final=data_final,
    )
    mensagem = criar_mensagem_rascunho(
        assunto=assunto,
        corpo=corpo,
        criada_por=usuario_responsavel,
        payload_email=payload,
    )
    mensagem.usuarios_alvo.add(reserva.criado_por)
    publicar_mensagem(mensagem, usuario=usuario_responsavel)
    return mensagem


def _conflito_deferido_queryset(ocorrencia: ReservaRecurso):
    """Monta o filtro de sobreposição contra reservas deferidas do mesmo objeto."""

    return ReservaRecurso.objects.filter(
        objeto=ocorrencia.objeto,
        data=ocorrencia.data,
        status=ReservaRecurso.Status.DEFERIDA,
        hora_inicio__lt=ocorrencia.hora_fim,
        hora_fim__gt=ocorrencia.hora_inicio,
    ).exclude(pk=ocorrencia.pk)


@transaction.atomic
def deferir_reserva(reserva: ReservaRecurso, *, fiscal):
    """Aplica a análise positiva à série inteira e cria a notificação correspondente."""

    reservas = list(_serie_queryset(reserva).select_for_update())
    if not reservas:
        raise ValidationError("Reserva não encontrada.")
    for ocorrencia in reservas:
        if ocorrencia.status != ReservaRecurso.Status.AGUARDANDO_APROVACAO:
            raise ValidationError("Somente solicitações aguardando aprovação podem ser deferidas.")
        if _conflito_deferido_queryset(ocorrencia).exists():
            raise ValidationError("O objeto selecionado já possui reserva deferida em horário conflitante.")

    for ocorrencia in reservas:
        ocorrencia.status = ReservaRecurso.Status.DEFERIDA
        ocorrencia.fiscal_responsavel = fiscal
        ocorrencia.justificativa_indeferimento = ""
        ocorrencia.save(update_fields=["status", "fiscal_responsavel", "justificativa_indeferimento", "atualizado_em"])
        registrar_evento(
            ocorrencia,
            ReservaRecursoEvento.Acao.DEFERIMENTO,
            usuario=fiscal,
            payload={"data": ocorrencia.data.isoformat(), "objeto_id": ocorrencia.objeto_id},
        )
    queryset = ReservaRecurso.objects.filter(pk__in=[oc.pk for oc in reservas]).order_by("data", "hora_inicio", "id")
    notificar_solicitante(queryset, usuario_responsavel=fiscal)
    return queryset


@transaction.atomic
def indeferir_reserva(reserva: ReservaRecurso, *, fiscal, justificativa):
    """Aplica a análise negativa à série inteira e notifica o solicitante."""

    reservas = list(_serie_queryset(reserva).select_for_update())
    if not reservas:
        raise ValidationError("Reserva não encontrada.")
    justificativa = justificativa.strip()
    for ocorrencia in reservas:
        if ocorrencia.status != ReservaRecurso.Status.AGUARDANDO_APROVACAO:
            raise ValidationError("Somente solicitações aguardando aprovação podem ser indeferidas.")
    for ocorrencia in reservas:
        ocorrencia.status = ReservaRecurso.Status.INDEFERIDA
        ocorrencia.fiscal_responsavel = fiscal
        ocorrencia.justificativa_indeferimento = justificativa
        ocorrencia.save(update_fields=["status", "fiscal_responsavel", "justificativa_indeferimento", "atualizado_em"])
        registrar_evento(
            ocorrencia,
            ReservaRecursoEvento.Acao.INDEFERIMENTO,
            usuario=fiscal,
            payload={"data": ocorrencia.data.isoformat(), "justificativa": justificativa},
        )
    queryset = ReservaRecurso.objects.filter(pk__in=[oc.pk for oc in reservas]).order_by("data", "hora_inicio", "id")
    notificar_solicitante(queryset, usuario_responsavel=fiscal)
    return queryset


@transaction.atomic
def cancelar_reserva_com_escopo(
    reserva: ReservaRecurso,
    *,
    usuario,
    apply_scope: str = "single",
    data_inicial: date | None = None,
    data_final: date | None = None,
    motivo_cancelamento: str = "",
):
    """Cancela uma ocorrência, a série inteira ou apenas um intervalo específico da série."""

    motivo_cancelamento = (motivo_cancelamento or "").strip()
    if not motivo_cancelamento:
        raise ValidationError("Informe o motivo do cancelamento.")

    reservas = list(
        _cancel_scope_queryset(
            reserva,
            apply_scope=apply_scope,
            data_inicial=data_inicial,
            data_final=data_final,
        ).select_for_update()
    )
    if not reservas:
        raise ValidationError("Reserva não encontrada.")
    reservas_ativas = [
        ocorrencia
        for ocorrencia in reservas
        if ocorrencia.status in {
            ReservaRecurso.Status.AGUARDANDO_APROVACAO,
            ReservaRecurso.Status.DEFERIDA,
        }
    ]
    if not reservas_ativas:
        raise ValidationError("Nenhuma reserva ativa foi encontrada no escopo selecionado para cancelamento.")

    for ocorrencia in reservas_ativas:
        ocorrencia.status = ReservaRecurso.Status.CANCELADA
        ocorrencia.save(update_fields=["status", "atualizado_em"])
        registrar_evento(
            ocorrencia,
            ReservaRecursoEvento.Acao.CANCELAMENTO,
            usuario=usuario,
            payload={
                "apply_scope": apply_scope,
                "data_inicial": data_inicial.isoformat() if data_inicial else "",
                "data_final": data_final.isoformat() if data_final else "",
                "motivo_cancelamento": motivo_cancelamento,
                "origem": "fluxo_fiscal" if reserva.criado_por_id != getattr(usuario, "id", None) else "fluxo_usuario",
            },
        )
    queryset = ReservaRecurso.objects.filter(pk__in=[oc.pk for oc in reservas_ativas]).order_by("data", "hora_inicio", "id")
    notificar_cancelamento(
        queryset,
        usuario_responsavel=usuario,
        motivo=motivo_cancelamento,
        apply_scope=apply_scope,
        data_inicial=data_inicial,
        data_final=data_final,
    )
    return reservas_ativas


def reserva_espacos_dashboard_context():
    """Produz os indicadores consolidados do dashboard do módulo."""

    base = ReservaRecurso.objects.select_related("criado_por", "criado_por__perfil", "objeto")
    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    reservas_mes = base.filter(data__gte=inicio_mes, data__month=hoje.month, data__year=hoje.year)
    deferidas_mes = reservas_mes.filter(status=ReservaRecurso.Status.DEFERIDA)
    indeferidas_mes = reservas_mes.filter(status=ReservaRecurso.Status.INDEFERIDA)
    pendentes_mes = reservas_mes.filter(status=ReservaRecurso.Status.AGUARDANDO_APROVACAO)

    objetos_ativos_mes = deferidas_mes.values("objeto_id").distinct().count()
    dias_com_reserva_mes = deferidas_mes.values("data").distinct().count()
    media_reservas_por_dia = round(deferidas_mes.count() / dias_com_reserva_mes, 2) if dias_com_reserva_mes else 0

    reservas_por_mes = (
        base.annotate(mes=TruncMonth("data"))
        .values("mes")
        .annotate(total=Count("id"))
        .order_by("mes")
    )
    objetos_top = (
        deferidas_mes.values("objeto__nome")
        .annotate(total=Count("id"))
        .order_by("-total", "objeto__nome")
    )[:10]
    total_objetos = ObjetoReservavel.objects.filter(ativo=True).count()

    return {
        "total_reservas_mes": reservas_mes.count(),
        "reservas_deferidas_mes": deferidas_mes.count(),
        "reservas_indeferidas_mes": indeferidas_mes.count(),
        "reservas_pendentes_mes": pendentes_mes.count(),
        "objetos_ativos_mes": objetos_ativos_mes,
        "objetos_cadastrados": total_objetos,
        "media_reservas_por_dia": media_reservas_por_dia,
        "mes_referencia": hoje.strftime("%m/%Y"),
        "grafico_reservas_meses": {
            "labels": [item["mes"].strftime("%m/%Y") for item in reservas_por_mes if item["mes"]],
            "values": [item["total"] for item in reservas_por_mes if item["mes"]],
        },
        "grafico_objetos_top": {
            "labels": [item["objeto__nome"] for item in objetos_top],
            "values": [item["total"] for item in objetos_top],
        },
    }
