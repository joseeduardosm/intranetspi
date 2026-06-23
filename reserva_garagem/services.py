"""Centraliza regras operacionais, conflitos e notificações do módulo."""

from __future__ import annotations

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone

from mensageria_assincrona.services import criar_mensagem_rascunho, publicar_mensagem

from .models import (
    ConfiguracaoReservaGaragem,
    ReservaGaragem,
    ReservaGaragemEvento,
    VagaGaragem,
)


def registrar_evento(reserva, acao, usuario=None, payload=None):
    """Grava a trilha mínima de auditoria da reserva de garagem."""

    return ReservaGaragemEvento.objects.create(
        reserva=reserva,
        usuario=usuario,
        acao=acao,
        payload=payload or {},
    )


def fiscal_group():
    """Obtém o grupo operacional configurado para os fiscais."""

    return ConfiguracaoReservaGaragem.singleton().grupo_fiscais


def user_is_fiscal(user) -> bool:
    """Identifica se o usuário faz parte do grupo operacional de análise."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    group = fiscal_group()
    return bool(group and user.groups.filter(pk=group.pk).exists())


def _format_date(value):
    """Formata datas no padrão brasileiro para mensagens e detalhes."""

    if not value:
        return "-"
    return value.strftime("%d/%m/%Y")


def _serie_queryset(reserva: ReservaGaragem):
    """Retorna a série completa quando houver, ou apenas a própria ocorrência."""

    if reserva.serie_id:
        return ReservaGaragem.objects.filter(serie_id=reserva.serie_id).order_by("data", "id")
    return ReservaGaragem.objects.filter(pk=reserva.pk)


def _cancel_scope_queryset(
    reserva: ReservaGaragem,
    *,
    apply_scope: str = "single",
    data_inicial: date | None = None,
    data_final: date | None = None,
):
    """Resolve quais ocorrências da reserva serão canceladas conforme o escopo solicitado."""

    if not reserva.serie_id or apply_scope == "single":
        return ReservaGaragem.objects.filter(pk=reserva.pk).order_by("data", "id")
    if apply_scope == "all":
        return ReservaGaragem.objects.filter(serie_id=reserva.serie_id).order_by("data", "id")
    if apply_scope == "range":
        if not (data_inicial and data_final):
            raise ValidationError("Informe a data inicial e a data final do cancelamento.")
        if data_final < data_inicial:
            raise ValidationError("A data final do cancelamento deve ser maior ou igual à data inicial.")
        queryset = ReservaGaragem.objects.filter(
            serie_id=reserva.serie_id,
            data__range=(data_inicial, data_final),
        ).order_by("data", "id")
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
    """Monta a mensagem interna enviada ao grupo fiscal quando nasce uma nova solicitação."""

    reserva = reservas.first()
    intervalo = _datas_serie_display(reservas)
    link_analise = reverse("reserva_garagem:fila_fiscal_analise", args=[reserva.pk])
    assunto = f"Nova solicitação de reserva de garagem #{reserva.pk}"
    corpo = (
        "Uma nova solicitação de reserva de garagem aguarda análise fiscal.\n\n"
        f"Solicitante: {reserva.responsavel}\n"
        f"Período: {intervalo}\n"
        f"Vaga solicitada: {reserva.vaga.nome_exibicao}\n"
        f"Placa: {reserva.placa_veiculo}\n"
        f"Veículo: {reserva.marca_veiculo} {reserva.modelo_veiculo} - {reserva.cor_veiculo}\n"
        f"Observações: {reserva.observacoes or '-'}"
    )
    payload = {
        "tipo": "nova_solicitacao_reserva_garagem",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "status": reserva.status,
        "vaga": reserva.vaga.nome_exibicao,
        "placa": reserva.placa_veiculo,
        "datas": [data.isoformat() for data in reservas.values_list("data", flat=True)],
        "link_analise": link_analise,
    }
    return assunto, corpo, payload


def _mensagem_reserva_deferida(reservas):
    """Monta assunto, corpo e payload para a notificação de deferimento."""

    reserva = reservas.first()
    assunto = f"Reserva de vaga deferida #{reserva.pk}"
    intervalo = _datas_serie_display(reservas)
    corpo = (
        f"Sua solicitação de reserva de vaga foi deferida.\n\n"
        f"Vaga: {reserva.vaga.nome_exibicao}\n"
        f"Período: {intervalo}\n"
        f"Placa: {reserva.placa_veiculo}\n"
        f"Veículo: {reserva.marca_veiculo} {reserva.modelo_veiculo} - {reserva.cor_veiculo}\n"
        f"Observações: {reserva.observacoes or '-'}"
    )
    payload = {
        "tipo": "deferimento_reserva_garagem",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "vaga": reserva.vaga.nome_exibicao,
        "placa": reserva.placa_veiculo,
        "marca": reserva.marca_veiculo,
        "modelo": reserva.modelo_veiculo,
        "cor": reserva.cor_veiculo,
        "status": reserva.status,
        "datas": [data.isoformat() for data in reservas.values_list("data", flat=True)],
    }
    return assunto, corpo, payload


def _mensagem_reserva_indeferida(reservas):
    """Monta a notificação textual do indeferimento."""

    reserva = reservas.first()
    assunto = f"Reserva de vaga indeferida #{reserva.pk}"
    intervalo = _datas_serie_display(reservas)
    corpo = (
        f"Sua solicitação de reserva de vaga foi indeferida.\n\n"
        f"Vaga: {reserva.vaga.nome_exibicao}\n"
        f"Período: {intervalo}\n"
        f"Placa: {reserva.placa_veiculo}\n"
        f"Justificativa: {reserva.justificativa_indeferimento}"
    )
    payload = {
        "tipo": "indeferimento_reserva_garagem",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "vaga": reserva.vaga.nome_exibicao,
        "placa": reserva.placa_veiculo,
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
    cancelamento_administrativo = reserva.solicitante_id != getattr(usuario_cancelamento, "id", None)
    origem_texto = "cancelada administrativamente" if cancelamento_administrativo else "cancelada"
    escopo = _scope_display(apply_scope, data_inicial, data_final)
    assunto = f"Reserva de vaga cancelada #{reserva.pk}"
    corpo = (
        f"Sua reserva de vaga foi {origem_texto}.\n\n"
        f"Vaga: {reserva.vaga.nome_exibicao}\n"
        f"Período: {intervalo}\n"
        f"Escopo do cancelamento: {escopo}\n"
        f"Placa: {reserva.placa_veiculo}\n"
        f"Cancelada por: {nome_cancelador}\n"
        f"Motivo do cancelamento: {motivo}\n"
        f"Observações: {reserva.observacoes or '-'}"
    )
    payload = {
        "tipo": "cancelamento_reserva_garagem",
        "reserva_id": reserva.pk,
        "serie_id": str(reserva.serie_id or ""),
        "vaga": reserva.vaga.nome_exibicao,
        "placa": reserva.placa_veiculo,
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
    if reserva.status == ReservaGaragem.Status.DEFERIDA:
        assunto, corpo, payload = _mensagem_reserva_deferida(reservas)
    elif reserva.status == ReservaGaragem.Status.INDEFERIDA:
        assunto, corpo, payload = _mensagem_reserva_indeferida(reservas)
    else:
        return None

    mensagem = criar_mensagem_rascunho(
        assunto=assunto,
        corpo=corpo,
        criada_por=usuario_responsavel,
        payload_email=payload,
    )
    mensagem.usuarios_alvo.add(reserva.solicitante)
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
    if not reserva or reserva.status != ReservaGaragem.Status.CANCELADA:
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
    mensagem.usuarios_alvo.add(reserva.solicitante)
    publicar_mensagem(mensagem, usuario=usuario_responsavel)
    return mensagem


@transaction.atomic
def deferir_reserva(reserva: ReservaGaragem, *, fiscal):
    """Aplica a análise positiva à série inteira e cria a notificação correspondente."""

    reservas = list(_serie_queryset(reserva).select_for_update())
    if not reservas:
        raise ValidationError("Reserva não encontrada.")
    for ocorrencia in reservas:
        if ocorrencia.status != ReservaGaragem.Status.AGUARDANDO_APROVACAO:
            raise ValidationError("Somente solicitações aguardando aprovação podem ser deferidas.")
        conflito_vaga = ReservaGaragem.objects.filter(
            vaga=ocorrencia.vaga,
            data=ocorrencia.data,
            status=ReservaGaragem.Status.DEFERIDA,
        ).exclude(pk=ocorrencia.pk)
        if conflito_vaga.exists():
            raise ValidationError("A vaga selecionada já possui reserva deferida em intervalo conflitante.")
        conflito_placa = ReservaGaragem.objects.filter(
            placa_veiculo__iexact=ocorrencia.placa_veiculo,
            data=ocorrencia.data,
        ).exclude(pk=ocorrencia.pk).exclude(status=ReservaGaragem.Status.CANCELADA)
        if conflito_placa.exists():
            raise ValidationError("A placa informada já possui reserva conflitante em uma das datas.")
        conflito_solicitante = ReservaGaragem.objects.filter(
            solicitante=ocorrencia.solicitante,
            data=ocorrencia.data,
        ).exclude(pk=ocorrencia.pk).exclude(status=ReservaGaragem.Status.CANCELADA)
        if conflito_solicitante.exists():
            raise ValidationError("O solicitante já possui reserva conflitante em uma das datas.")

    for ocorrencia in reservas:
        ocorrencia.status = ReservaGaragem.Status.DEFERIDA
        ocorrencia.fiscal_responsavel = fiscal
        ocorrencia.justificativa_indeferimento = ""
        ocorrencia.save(update_fields=["status", "fiscal_responsavel", "justificativa_indeferimento", "atualizado_em"])
        registrar_evento(
            ocorrencia,
            ReservaGaragemEvento.Acao.DEFERIMENTO,
            usuario=fiscal,
            payload={"data": ocorrencia.data.isoformat(), "vaga_id": ocorrencia.vaga_id},
        )
    queryset = ReservaGaragem.objects.filter(pk__in=[oc.pk for oc in reservas]).order_by("data", "id")
    notificar_solicitante(queryset, usuario_responsavel=fiscal)
    return queryset


@transaction.atomic
def indeferir_reserva(reserva: ReservaGaragem, *, fiscal, justificativa):
    """Aplica a análise negativa à série inteira e notifica o solicitante."""

    reservas = list(_serie_queryset(reserva).select_for_update())
    if not reservas:
        raise ValidationError("Reserva não encontrada.")
    justificativa = justificativa.strip()
    for ocorrencia in reservas:
        if ocorrencia.status != ReservaGaragem.Status.AGUARDANDO_APROVACAO:
            raise ValidationError("Somente solicitações aguardando aprovação podem ser indeferidas.")
    for ocorrencia in reservas:
        ocorrencia.status = ReservaGaragem.Status.INDEFERIDA
        ocorrencia.fiscal_responsavel = fiscal
        ocorrencia.justificativa_indeferimento = justificativa
        ocorrencia.save(update_fields=["status", "fiscal_responsavel", "justificativa_indeferimento", "atualizado_em"])
        registrar_evento(
            ocorrencia,
            ReservaGaragemEvento.Acao.INDEFERIMENTO,
            usuario=fiscal,
            payload={"data": ocorrencia.data.isoformat(), "justificativa": justificativa},
        )
    queryset = ReservaGaragem.objects.filter(pk__in=[oc.pk for oc in reservas]).order_by("data", "id")
    notificar_solicitante(queryset, usuario_responsavel=fiscal)
    return queryset


@transaction.atomic
def cancelar_reserva(reserva: ReservaGaragem, *, usuario):
    """Cancela a série ou ocorrência ativa e notifica o solicitante sobre a liberação da vaga."""

    return cancelar_reserva_com_escopo(
        reserva,
        usuario=usuario,
        motivo_cancelamento="Cancelamento da reserva.",
    )


@transaction.atomic
def cancelar_reserva_com_escopo(
    reserva: ReservaGaragem,
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
            ReservaGaragem.Status.AGUARDANDO_APROVACAO,
            ReservaGaragem.Status.DEFERIDA,
        }
    ]
    if not reservas_ativas:
        raise ValidationError("Nenhuma reserva ativa foi encontrada no escopo selecionado para cancelamento.")
    for ocorrencia in reservas_ativas:
        ocorrencia.status = ReservaGaragem.Status.CANCELADA
        ocorrencia.save(update_fields=["status", "atualizado_em"])
        registrar_evento(
            ocorrencia,
            ReservaGaragemEvento.Acao.CANCELAMENTO,
            usuario=usuario,
            payload={
                "apply_scope": apply_scope,
                "data_inicial": data_inicial.isoformat() if data_inicial else "",
                "data_final": data_final.isoformat() if data_final else "",
                "motivo_cancelamento": motivo_cancelamento,
                "origem": "fluxo_fiscal" if reserva.solicitante_id != getattr(usuario, "id", None) else "fluxo_usuario",
            },
        )
    queryset = ReservaGaragem.objects.filter(pk__in=[oc.pk for oc in reservas_ativas]).order_by("data", "id")
    notificar_cancelamento(
        queryset,
        usuario_responsavel=usuario,
        motivo=motivo_cancelamento,
        apply_scope=apply_scope,
        data_inicial=data_inicial,
        data_final=data_final,
    )
    return reservas_ativas


def reserva_garagem_dashboard_context():
    """Produz os indicadores consolidados do dashboard do módulo."""

    base = ReservaGaragem.objects.select_related("solicitante", "solicitante__perfil", "vaga")
    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    fim_mes = (inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    ativas = VagaGaragem.objects.filter(ativo=True).count()
    reservas_mes = base.filter(data__range=(inicio_mes, fim_mes))
    deferidas_mes = reservas_mes.filter(status=ReservaGaragem.Status.DEFERIDA)
    dias_mes = (fim_mes - inicio_mes).days + 1
    ocupacao_por_dia = []
    for offset in range(dias_mes):
        dia = inicio_mes + timedelta(days=offset)
        ocupadas = deferidas_mes.filter(data=dia).values("vaga_id").distinct().count()
        percentual = round((ocupadas / ativas) * 100, 2) if ativas else 0
        ocupacao_por_dia.append({"data": dia, "ocupadas": ocupadas, "percentual": percentual})
    media_ocupacao = round(sum(item["percentual"] for item in ocupacao_por_dia) / dias_mes, 2) if dias_mes else 0

    vagas_top = (
        deferidas_mes.values("vaga__nome", "vaga__localizacao")
        .annotate(total=Count("id"))
        .order_by("-total", "vaga__nome")
    )[:10]
    reservas_por_mes = (
        base.annotate(mes_ref=TruncMonth("data"))
        .values("mes_ref")
        .annotate(total=Count("id"))
        .order_by("mes_ref")
    )

    return {
        "total_reservas_mes": reservas_mes.count(),
        "reservas_deferidas_mes": deferidas_mes.count(),
        "percentual_medio_ocupacao": media_ocupacao,
        "mes_referencia": hoje.strftime("%m/%Y"),
        "ocupacao_por_dia": ocupacao_por_dia,
        "grafico_ocupacao_media": {
            "labels": [item["data"].strftime("%d/%m") for item in ocupacao_por_dia],
            "values": [item["percentual"] for item in ocupacao_por_dia],
        },
        "grafico_vagas_top": {
            "labels": [
                f"{item['vaga__nome']}" + (f" - {item['vaga__localizacao']}" if item["vaga__localizacao"] else "")
                for item in vagas_top
            ],
            "values": [item["total"] for item in vagas_top],
        },
        "grafico_reservas_meses": {
            "labels": [item["mes_ref"].strftime("%m/%Y") for item in reservas_por_mes if item["mes_ref"]],
            "values": [item["total"] for item in reservas_por_mes if item["mes_ref"]],
        },
    }
