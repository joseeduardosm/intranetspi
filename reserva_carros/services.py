# Criado por OpenAI Codex em 12/06/2026
# Centraliza regras operacionais, validações de conflito e notificações do módulo.

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from mensageria_assincrona.services import criar_mensagem_rascunho, publicar_mensagem

from .models import ConfiguracaoReservaCarros, ReservaCarro, ReservaCarroEvento, ReservaCarroPassageiro


User = get_user_model()


def registrar_evento(reserva, acao, usuario=None, payload=None):
    """Grava a trilha mínima de auditoria da reserva de carro."""

    return ReservaCarroEvento.objects.create(
        reserva=reserva,
        usuario=usuario,
        acao=acao,
        payload=payload or {},
    )


def fiscal_group():
    """Obtém o grupo operacional configurado para os fiscais."""

    return ConfiguracaoReservaCarros.singleton().grupo_fiscais


def user_is_fiscal(user) -> bool:
    """Identifica se o usuário faz parte do grupo operacional de análise."""

    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    group = fiscal_group()
    return bool(group and user.groups.filter(pk=group.pk).exists())


def sync_passageiros(reserva: ReservaCarro, passageiros):
    """Sincroniza os passageiros escolhidos no formulário com a tabela relacional."""

    selected_ids = {usuario.pk for usuario in passageiros}
    atuais = ReservaCarroPassageiro.objects.filter(reserva=reserva)
    atuais_ids = set(atuais.values_list("usuario_id", flat=True))
    for usuario in passageiros:
        ReservaCarroPassageiro.objects.get_or_create(reserva=reserva, usuario=usuario)
    atuais.exclude(usuario_id__in=selected_ids).delete()
    return {"adicionados": len(selected_ids - atuais_ids), "removidos": len(atuais_ids - selected_ids)}


def _overlap_q(inicio, fim):
    """Monta o filtro de sobreposição para janelas operacionais deferidas."""

    return Q(inicio_bloqueio_em__lt=fim) & Q(fim_bloqueio_em__gt=inicio)


def conflitos_deferimento(*, reserva, carro, motorista, inicio_bloqueio_em, fim_bloqueio_em):
    """Retorna conflitos ativos de carro e motorista para a janela final da viagem."""

    base = ReservaCarro.objects.filter(status=ReservaCarro.Status.DEFERIDA).exclude(pk=reserva.pk)
    conflitos = {"carro": None, "motorista": None}
    if carro:
        conflitos["carro"] = base.filter(carro=carro).filter(_overlap_q(inicio_bloqueio_em, fim_bloqueio_em)).first()
    if motorista:
        conflitos["motorista"] = base.filter(motorista=motorista).filter(_overlap_q(inicio_bloqueio_em, fim_bloqueio_em)).first()
    return conflitos


def _format_dt(value):
    """Formata datas em horário local para mensagens e detalhes."""

    if not value:
        return "-"
    return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")


def _mensagem_reserva_deferida(reserva):
    """Monta assunto, corpo e payload para a notificação de deferimento."""

    passageiros = ", ".join(
        vinculo.usuario.get_full_name() or vinculo.usuario.username
        for vinculo in reserva.passageiros_vinculos.select_related("usuario")
    )
    if not passageiros:
        passageiros = "Sem passageiros adicionais cadastrados"
    assunto = f"Viagem deferida #{reserva.pk}"
    corpo = (
        f"Sua solicitação de viagem foi deferida.\n\n"
        f"Saída planejada: {_format_dt(reserva.saida_planejada_em)}\n"
        f"Retorno planejado: {_format_dt(reserva.retorno_planejado_em)}\n"
        f"Janela operacional: {reserva.janela_operacional_display}\n"
        f"Destino: {reserva.destino_endereco}\n"
        f"Permanência: {reserva.get_modo_destino_display()}\n"
        f"Carro: {reserva.carro.nome_exibicao if reserva.carro_id else '-'}\n"
        f"Motorista: {reserva.motorista.nome_completo if reserva.motorista_id else '-'}\n"
        f"Motivo: {reserva.motivo_viagem}\n"
    )
    payload = {
        "tipo": "deferimento_reserva_carro",
        "reserva_id": reserva.pk,
        "saida_planejada_em": reserva.saida_planejada_em.isoformat(),
        "retorno_planejado_em": reserva.retorno_planejado_em.isoformat(),
        "inicio_bloqueio_em": reserva.inicio_bloqueio_em.isoformat() if reserva.inicio_bloqueio_em else "",
        "fim_bloqueio_em": reserva.fim_bloqueio_em.isoformat() if reserva.fim_bloqueio_em else "",
        "destino": reserva.destino_endereco,
        "modo_destino": reserva.modo_destino,
        "carro": reserva.carro.nome_exibicao if reserva.carro_id else "",
        "motorista": reserva.motorista.nome_completo if reserva.motorista_id else "",
    }
    return assunto, corpo, payload


def _mensagem_reserva_indeferida(reserva):
    """Monta a notificação textual do indeferimento."""

    assunto = f"Viagem indeferida #{reserva.pk}"
    corpo = (
        f"Sua solicitação de viagem foi indeferida.\n\n"
        f"Saída planejada: {_format_dt(reserva.saida_planejada_em)}\n"
        f"Retorno planejado: {_format_dt(reserva.retorno_planejado_em)}\n"
        f"Destino: {reserva.destino_endereco}\n"
        f"Justificativa: {reserva.justificativa_indeferimento}"
    )
    payload = {
        "tipo": "indeferimento_reserva_carro",
        "reserva_id": reserva.pk,
        "saida_planejada_em": reserva.saida_planejada_em.isoformat(),
        "retorno_planejado_em": reserva.retorno_planejado_em.isoformat(),
        "justificativa": reserva.justificativa_indeferimento,
    }
    return assunto, corpo, payload


def notificar_solicitante(reserva: ReservaCarro, usuario_responsavel=None):
    """Cria e publica a mensagem assíncrona após decisão fiscal."""

    if reserva.status == ReservaCarro.Status.DEFERIDA:
        assunto, corpo, payload = _mensagem_reserva_deferida(reserva)
    elif reserva.status == ReservaCarro.Status.INDEFERIDA:
        assunto, corpo, payload = _mensagem_reserva_indeferida(reserva)
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


@transaction.atomic
def deferir_reserva(reserva: ReservaCarro, *, fiscal, carro, motorista, deslocamento_ida_minutos, deslocamento_retorno_minutos):
    """Aplica a análise positiva, valida conflitos e cria a notificação correspondente."""

    reserva = ReservaCarro.objects.select_for_update().get(pk=reserva.pk)
    if reserva.status != ReservaCarro.Status.AGUARDANDO_APROVACAO:
        raise ValidationError("Somente solicitações aguardando aprovação podem ser deferidas.")

    inicio = reserva.saida_planejada_em - timedelta(minutes=deslocamento_ida_minutos)
    fim = reserva.retorno_planejado_em + timedelta(minutes=deslocamento_retorno_minutos)
    conflitos = conflitos_deferimento(
        reserva=reserva,
        carro=carro,
        motorista=motorista,
        inicio_bloqueio_em=inicio,
        fim_bloqueio_em=fim,
    )
    if conflitos["carro"]:
        raise ValidationError("O carro selecionado já possui viagem deferida em intervalo conflitante.")
    if conflitos["motorista"]:
        raise ValidationError("O motorista selecionado já possui viagem deferida em intervalo conflitante.")

    reserva.status = ReservaCarro.Status.DEFERIDA
    reserva.fiscal_responsavel = fiscal
    reserva.deslocamento_ida_minutos = deslocamento_ida_minutos
    reserva.deslocamento_retorno_minutos = deslocamento_retorno_minutos
    reserva.carro = carro
    reserva.motorista = motorista
    reserva.justificativa_indeferimento = ""
    reserva.inicio_bloqueio_em = inicio
    reserva.fim_bloqueio_em = fim
    reserva.save()
    registrar_evento(
        reserva,
        ReservaCarroEvento.Acao.DEFERIMENTO,
        usuario=fiscal,
        payload={
            "carro_id": carro.pk,
            "motorista_id": motorista.pk,
            "inicio_bloqueio_em": inicio.isoformat(),
            "fim_bloqueio_em": fim.isoformat(),
        },
    )
    notificar_solicitante(reserva, usuario_responsavel=fiscal)
    return reserva


@transaction.atomic
def indeferir_reserva(reserva: ReservaCarro, *, fiscal, justificativa):
    """Aplica a análise negativa e notifica o solicitante."""

    reserva = ReservaCarro.objects.select_for_update().get(pk=reserva.pk)
    if reserva.status != ReservaCarro.Status.AGUARDANDO_APROVACAO:
        raise ValidationError("Somente solicitações aguardando aprovação podem ser indeferidas.")

    reserva.status = ReservaCarro.Status.INDEFERIDA
    reserva.fiscal_responsavel = fiscal
    reserva.justificativa_indeferimento = justificativa.strip()
    reserva.carro = None
    reserva.motorista = None
    reserva.deslocamento_ida_minutos = None
    reserva.deslocamento_retorno_minutos = None
    reserva.inicio_bloqueio_em = None
    reserva.fim_bloqueio_em = None
    reserva.save()
    registrar_evento(
        reserva,
        ReservaCarroEvento.Acao.INDEFERIMENTO,
        usuario=fiscal,
        payload={"justificativa": reserva.justificativa_indeferimento},
    )
    notificar_solicitante(reserva, usuario_responsavel=fiscal)
    return reserva


@transaction.atomic
def cancelar_reserva(reserva: ReservaCarro, *, usuario):
    """Permite o cancelamento apenas antes da análise do fiscal."""

    reserva = ReservaCarro.objects.select_for_update().get(pk=reserva.pk)
    if reserva.status != ReservaCarro.Status.AGUARDANDO_APROVACAO:
        raise ValidationError("Somente solicitações aguardando aprovação podem ser canceladas.")
    reserva.status = ReservaCarro.Status.CANCELADA
    reserva.save(update_fields=["status", "atualizado_em"])
    registrar_evento(reserva, ReservaCarroEvento.Acao.CANCELAMENTO, usuario=usuario)
    return reserva


def reserva_carros_dashboard_context():
    """Produz os indicadores consolidados do dashboard do módulo."""

    base = ReservaCarro.objects.select_related("solicitante", "solicitante__perfil", "carro")
    hoje = timezone.localdate()
    inicio_mes = hoje.replace(day=1)
    fim_mes = hoje.replace(day=28) + timedelta(days=4)
    fim_mes = fim_mes.replace(day=1) - timedelta(days=1)
    mes_qs = base.filter(saida_planejada_em__date__range=(inicio_mes, fim_mes))
    reservas_deferidas = mes_qs.filter(status=ReservaCarro.Status.DEFERIDA)
    carros_top = (
        reservas_deferidas.values("carro__marca", "carro__modelo", "carro__placa")
        .annotate(total=Count("id"))
        .order_by("-total", "carro__marca", "carro__modelo")
    )[:10]
    destinos_top = (
        mes_qs.values("destino_endereco")
        .annotate(total=Count("id"))
        .order_by("-total", "destino_endereco")
    )[:10]
    usuarios_top = (
        mes_qs.values("solicitante__username", "solicitante__first_name")
        .annotate(total=Count("id"))
        .order_by("-total", "solicitante__username")
    )[:10]
    status_top = (
        mes_qs.values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )
    return {
        "total_viagens_mes": mes_qs.count(),
        "viagens_deferidas_mes": reservas_deferidas.count(),
        "mes_referencia": hoje.strftime("%m/%Y"),
        "grafico_carros_top": {
            "labels": [f"{item['carro__marca']} {item['carro__modelo']} - {item['carro__placa']}" for item in carros_top],
            "values": [item["total"] for item in carros_top],
        },
        "grafico_destinos_top": {
            "labels": [item["destino_endereco"] for item in destinos_top],
            "values": [item["total"] for item in destinos_top],
        },
        "grafico_usuarios_top": {
            "labels": [item["solicitante__first_name"] or item["solicitante__username"] for item in usuarios_top],
            "values": [item["total"] for item in usuarios_top],
        },
        "status_periodo": list(status_top),
    }
