# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Centralizar cálculos de vigência, execução financeira, qualidade e retroatividade.

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone


ZERO = Decimal('0.00')
CONTRATO_NUMERO_RE = re.compile(r'^(?P<sequencial>\d{3})/(?P<ano>\d{4})$')


def quantize_money(value):
    """Padroniza valores monetários com duas casas decimais."""

    return (value or ZERO).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def parse_numero_contrato(value):
    """Extrai sequência e ano do número no formato NNN/AAAA."""

    match = CONTRATO_NUMERO_RE.match((value or '').strip())
    if not match:
        return None
    return int(match.group('sequencial')), int(match.group('ano'))


def numero_contrato_por_ano(ano):
    """Calcula o próximo número sequencial do contrato para o ano informado."""

    from .models import Contrato

    maior = 0
    suffix = f'/{ano}'
    for numero in Contrato.objects.filter(numero_contrato__endswith=suffix).values_list('numero_contrato', flat=True):
        parsed = parse_numero_contrato(numero)
        if parsed and parsed[1] == ano:
            maior = max(maior, parsed[0])
    return f'{maior + 1:03d}/{ano}'


def add_months(base_date, months):
    """Adiciona meses preservando o último dia válido do mês de destino."""

    if not base_date:
        return None
    month_index = base_date.month - 1 + int(months or 0)
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base_date.day, last_day)
    return date(year, month, day)


def inclusive_end_date(start_date, months):
    """Converte uma vigência em meses para a última data do período correspondente."""

    final_date = add_months(start_date, months)
    if not final_date:
        return None
    return final_date - timedelta(days=1)


def full_months_between(start_date, end_date):
    """Conta meses completos entre duas datas para os indicadores de prazo."""

    if not start_date or not end_date or end_date < start_date:
        return 0
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return max(months, 0)


def periodo_texto(utilizado, total):
    """Formata indicadores no padrão X/Y meses usado pelo módulo."""

    return f'{utilizado}/{total} meses'


def contrato_total_itens(contrato):
    """Soma os subtotais dos itens do contrato."""

    total = contrato.itens.aggregate(total=Sum('valor_subtotal')).get('total') or ZERO
    return quantize_money(total)


def contrato_total_prorrogacoes(contrato):
    """Soma os meses de todos os termos aditivos de prorrogação."""

    total = contrato.aditivos.aggregate(total=Sum('quantidade_meses')).get('total') or 0
    return int(total)


def contrato_prazo_total_meses(contrato):
    """Retorna a vigência acumulada prevista considerando prorrogações."""

    return int(contrato.prazo_inicial_meses or 0) + contrato_total_prorrogacoes(contrato)


def contrato_data_final_vigente(contrato):
    """Obtém a data final vigente a partir do último aditivo ou do prazo inicial."""

    ultimo = contrato.aditivos.order_by('data_termino', 'id').last()
    if ultimo and ultimo.data_termino:
        return ultimo.data_termino
    return inclusive_end_date(contrato.data_inicio_vigencia, contrato.prazo_inicial_meses)


def contrato_data_limite_ordinaria(contrato):
    """Calcula a data limite da vigência ordinária do contrato."""

    return inclusive_end_date(contrato.data_inicio_vigencia, contrato.vigencia_maxima_meses)


def contrato_regime(contrato):
    """Define o regime contratual com base no total de meses consumidos/previstos."""

    total_meses = contrato_prazo_total_meses(contrato)
    ordinario = int(contrato.vigencia_maxima_meses or 0)
    if total_meses <= ordinario:
        return contrato.Regime.ORDINARIO
    if total_meses <= ordinario + 12:
        return contrato.Regime.EXCEPCIONAL
    return contrato.Regime.EMERGENCIAL


def contrato_situacao(contrato, reference_date=None):
    """Calcula a situação operacional do contrato a partir do calendário e travas manuais."""

    today = reference_date or timezone.localdate()
    if contrato.situacao_forcada == contrato.Situacao.SUSPENSO:
        return contrato.Situacao.SUSPENSO
    if contrato.situacao_forcada == contrato.Situacao.ENCERRADO:
        return contrato.Situacao.ENCERRADO
    data_final = contrato_data_final_vigente(contrato)
    if not data_final:
        return contrato.Situacao.VIGENTE
    if today > data_final:
        return contrato.Situacao.ENCERRADO
    dias_restantes = (data_final - today).days
    if dias_restantes <= 180:
        return contrato.Situacao.A_VENCER
    return contrato.Situacao.VIGENTE


def contrato_alerta(contrato, reference_date=None):
    """Mapeia o alerta visual da listagem principal a partir dos dias restantes."""

    today = reference_date or timezone.localdate()
    situacao = contrato_situacao(contrato, today)
    if situacao == contrato.Situacao.ENCERRADO:
        return 'cinza'
    data_final = contrato_data_final_vigente(contrato)
    if not data_final:
        return 'verde'
    dias_restantes = (data_final - today).days
    if dias_restantes <= 30:
        return 'preto'
    if dias_restantes <= 60:
        return 'roxo'
    if dias_restantes <= 90:
        return 'vermelho'
    if dias_restantes <= 120:
        return 'laranja'
    if dias_restantes <= 180:
        return 'amarelo'
    return 'verde'


def contrato_prazo_atual_texto(contrato, reference_date=None):
    """Calcula o indicador de prazo atual dentro da vigência vigente."""

    today = reference_date or timezone.localdate()
    data_final = contrato_data_final_vigente(contrato) or today
    if today > data_final:
        fim_referencia = data_final
    else:
        fim_referencia = today
    meses = full_months_between(contrato.data_inicio_vigencia, fim_referencia)
    total = contrato_prazo_total_meses(contrato)
    return periodo_texto(meses, total)


def contrato_periodo_acumulado_texto(contrato, reference_date=None):
    """Calcula o indicador acumulado em relação ao limite máximo ordinário."""

    today = reference_date or timezone.localdate()
    data_final = contrato_data_final_vigente(contrato) or today
    fim_referencia = min(today, data_final)
    meses = full_months_between(contrato.data_inicio_vigencia, fim_referencia)
    total = int(contrato.vigencia_maxima_meses or 0)
    return periodo_texto(meses, total)


def snapshot_modelo_qualidade(modelo):
    """Converte o modelo vigente em um snapshot serializável para auditoria."""

    grupos = []
    for grupo in modelo.grupos.order_by('ordem', 'id'):
        criterios = []
        for criterio in grupo.criterios.order_by('ordem', 'id'):
            criterios.append(
                {
                    'id': criterio.id,
                    'nome': criterio.nome,
                    'peso': str(criterio.peso),
                    'pontuacao_maxima': str(criterio.pontuacao_maxima),
                }
            )
        grupos.append(
            {
                'id': grupo.id,
                'nome': grupo.nome,
                'peso': str(grupo.peso),
                'criterios': criterios,
            }
        )
    return {
        'modelo_id': modelo.id,
        'modelo_nome': modelo.nome,
        'grupos': grupos,
    }


def recalcular_avaliacao(competencia):
    """Atualiza percentual, desconto e valor final com base nas notas registradas."""

    avaliacao = getattr(competencia, 'avaliacao_qualidade', None)
    if not avaliacao:
        return

    total_obtido = Decimal('0')
    total_possivel = Decimal('0')
    for item in avaliacao.itens.select_related('criterio').all():
        total_obtido += item.nota_obtida
        total_possivel += item.criterio.pontuacao_maxima

    if total_possivel <= 0:
        avaliacao.percentual_desempenho = ZERO
    else:
        avaliacao.percentual_desempenho = quantize_money((total_obtido / total_possivel) * Decimal('100'))

    avaliacao.percentual_desconto = quantize_money(Decimal('100') - avaliacao.percentual_desempenho)
    valor_medido = competencia.valor_medido or ZERO
    avaliacao.valor_ajuste = quantize_money((valor_medido * avaliacao.percentual_desconto) / Decimal('100'))
    avaliacao.valor_final_ajustado = quantize_money(valor_medido - avaliacao.valor_ajuste)
    type(avaliacao).objects.filter(pk=avaliacao.pk).update(
        percentual_desempenho=avaliacao.percentual_desempenho,
        percentual_desconto=avaliacao.percentual_desconto,
        valor_ajuste=avaliacao.valor_ajuste,
        valor_final_ajustado=avaliacao.valor_final_ajustado,
    )


def recalcular_competencia(competencia):
    """Recalcula totais financeiros e status derivado da competência."""

    total_medicoes = competencia.medicoes.aggregate(total=Sum('valor_subtotal')).get('total') or ZERO
    competencia.valor_medido = quantize_money(total_medicoes)
    avaliacao = getattr(competencia, 'avaliacao_qualidade', None)
    if avaliacao and avaliacao.valor_final_ajustado is not None:
        competencia.valor_liberado = quantize_money(avaliacao.valor_final_ajustado)
    else:
        competencia.valor_liberado = competencia.valor_medido

    todos_ok = not competencia.checklist_itens.filter(obrigatorio=True, concluido=False).exists()
    novo_status = competencia.status
    if competencia.status == competencia.Status.RASCUNHO and todos_ok:
        novo_status = competencia.Status.APTO_LIBERACAO
    type(competencia).objects.filter(pk=competencia.pk).update(
        valor_medido=competencia.valor_medido,
        valor_liberado=competencia.valor_liberado,
        status=novo_status,
    )
    competencia.status = novo_status


def criar_checklist_competencia(competencia):
    """Replica o checklist-modelo atual do contrato para uma competência específica."""

    if competencia.checklist_itens.exists():
        return
    for modelo in competencia.contrato.checklist_modelos.order_by('ordem', 'id'):
        competencia.checklist_itens.create(
            titulo=modelo.titulo,
            descricao=modelo.descricao,
            obrigatorio=modelo.obrigatorio,
            ordem=modelo.ordem,
        )


def calcular_memorias_retroativas(evento):
    """Gera a memória de cálculo retroativo por competência afetada pelo reajuste."""

    memorias = []
    for item_evento in evento.itens.select_related('item_contrato').all():
        medicoes = item_evento.item_contrato.medicoes.filter(
            competencia__periodo_inicio__gte=evento.data_base,
            competencia__periodo_inicio__lt=evento.data_aplicacao,
        ).select_related('competencia')
        for medicao in medicoes:
            diferenca_unitaria = quantize_money(item_evento.valor_reajustado - medicao.valor_unitario_aplicado)
            diferenca_total = quantize_money(diferenca_unitaria * medicao.quantidade)
            memoria = evento.memorias.update_or_create(
                competencia=medicao.competencia,
                item_contrato=item_evento.item_contrato,
                defaults={
                    'quantidade_base': medicao.quantidade,
                    'valor_unitario_anterior': medicao.valor_unitario_aplicado,
                    'valor_unitario_reajustado': item_evento.valor_reajustado,
                    'diferenca_total': diferenca_total,
                },
            )[0]
            memorias.append(memoria)
    return memorias
