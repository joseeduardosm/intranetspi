# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Centralizar regras do fluxo de checklist, competências, medição, avaliação e pagamento do Contratos V2.

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from contratos.services import inclusive_end_date, iterar_periodos_competencia, quantize_money


ZERO = Decimal('0.00')


def usuario_eh_admin_sistema(user):
    """Considera como administradores operadores com privilégios globais do portal."""

    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def usuario_pode_gerir_contrato_v2(user, contrato):
    """Gestor do contrato e administradores podem gerir cadastros e autorizações."""

    return bool(
        user
        and user.is_authenticated
        and (
            usuario_eh_admin_sistema(user)
            or user.pk == contrato.gestor_contrato_id
        )
    )


def usuario_pode_preencher_checklist_v2(user, contrato):
    """Checklist pode ser alimentado pelos fiscais, pelo gestor e por administradores."""

    return bool(
        user
        and user.is_authenticated
        and (
            usuario_pode_gerir_contrato_v2(user, contrato)
            or user.pk == contrato.fiscal_administrativo_id
            or user.pk == contrato.fiscal_tecnico_id
        )
    )


def usuario_pode_preencher_avaliacao_v2(user, contrato):
    """A avaliação segue a mesma regra operacional do checklist."""

    return usuario_pode_preencher_checklist_v2(user, contrato)


def usuario_pode_preencher_medicao_v2(user, contrato):
    """Nesta primeira fase a medição fica com gestor e administradores."""

    return usuario_pode_gerir_contrato_v2(user, contrato)


def competencia_v2_esta_fechada(competencia):
    """Competências pagas ou canceladas ficam congeladas para preservar trilha histórica."""

    return competencia.status in {
        competencia.Status.PAGA,
        competencia.Status.CANCELADA,
    }


def competencia_v2_exige_avaliacao(competencia):
    """A competência exige avaliação quando nasceu vinculada a uma versão de formulário."""

    return bool(competencia.formulario_avaliacao_snapshot)


def validar_competencia_v2_editavel(competencia):
    """Impede alterações operacionais em competências já encerradas."""

    if competencia_v2_esta_fechada(competencia):
        raise ValidationError('Esta competência já foi encerrada e não pode mais ser alterada.')


def _snapshot_checklist_modelo(modelo):
    """Serializa a versão do checklist com todos os itens para replicação nas competências."""

    return {
        'id': modelo.pk,
        'nome': modelo.nome,
        'descricao': modelo.descricao,
        'observacoes': modelo.observacoes,
        'ativo': modelo.ativo,
        'itens': [
            {
                'ordem': item.ordem,
                'titulo': item.titulo,
                'descricao': item.descricao,
                'obrigatorio': item.obrigatorio,
            }
            for item in modelo.itens.order_by('ordem', 'id')
        ],
    }


def _snapshot_formulario_avaliacao(formulario):
    """Congela a definição da avaliação no momento em que a competência nasce."""

    return {
        'id': formulario.pk,
        'nome': formulario.nome,
        'descricao': formulario.descricao,
        'observacoes': formulario.observacoes,
        'escala': [
            {
                'ordem': nota.ordem,
                'valor': str(nota.valor),
                'legenda': nota.legenda,
            }
            for nota in formulario.escalas.order_by('ordem', 'id')
        ],
        'faixas_liberacao': [
            {
                'ordem': faixa.ordem,
                'nota_minima': str(faixa.nota_minima),
                'nota_maxima': str(faixa.nota_maxima) if faixa.nota_maxima is not None else '',
                'percentual_liberacao': str(faixa.percentual_liberacao),
            }
            for faixa in formulario.faixas_liberacao.order_by('ordem', 'id')
        ],
        'grupos': [
            {
                'ordem': grupo.ordem,
                'nome': grupo.nome,
                'descricao': grupo.descricao,
                'itens': [
                    {
                        'ordem': item.ordem,
                        'descricao': item.descricao,
                        'peso_percentual': str(item.peso_percentual),
                        'observacoes_padrao': item.observacoes_padrao,
                    }
                    for item in grupo.itens.order_by('ordem', 'id')
                ],
            }
            for grupo in formulario.grupos.order_by('ordem', 'id')
        ],
    }


def atualizar_checklist_snapshot_competencia_v2(competencia, modelo):
    """Replica a versão ativa do checklist para uma competência ainda aberta."""

    from .models import ChecklistCompetenciaItemV2

    validar_competencia_v2_editavel(competencia)
    competencia.checklist_modelo_snapshot = _snapshot_checklist_modelo(modelo)
    competencia.save(update_fields=['checklist_modelo_snapshot', 'atualizado_em'])
    competencia.checklist_itens.all().delete()
    for item_snapshot in competencia.checklist_modelo_snapshot.get('itens', []):
        ChecklistCompetenciaItemV2.objects.create(
            competencia=competencia,
            ordem=item_snapshot['ordem'],
            titulo=item_snapshot['titulo'],
            descricao=item_snapshot.get('descricao', ''),
            obrigatorio=item_snapshot.get('obrigatorio', True),
        )
    recalcular_competencia_v2(competencia)


def sincronizar_checklist_ativo_contrato_v2(contrato):
    """Aplica o checklist ativo às competências ainda não encerradas do contrato."""

    modelo = contrato.checklist_ativo
    if modelo is None:
        return
    for competencia in contrato.competencias.exclude(
        status__in=[
            contrato.competencias.model.Status.PAGA,
            contrato.competencias.model.Status.CANCELADA,
        ]
    ):
        atualizar_checklist_snapshot_competencia_v2(competencia, modelo)


def criar_avaliacao_shell_competencia_v2(competencia, formulario):
    """Cria a avaliação vazia já com snapshot e itens-resposta vinculados à competência."""

    from .models import AvaliacaoCompetenciaItemRespostaV2, AvaliacaoQualidadeCompetenciaV2

    if competencia.avaliacao_qualidade_segura is not None:
        return competencia.avaliacao_qualidade_segura

    snapshot = _snapshot_formulario_avaliacao(formulario)
    avaliacao = AvaliacaoQualidadeCompetenciaV2.objects.create(
        competencia=competencia,
        formulario=formulario,
        formulario_snapshot=snapshot,
    )
    for grupo in snapshot.get('grupos', []):
        for item in grupo.get('itens', []):
            AvaliacaoCompetenciaItemRespostaV2.objects.create(
                avaliacao=avaliacao,
                grupo_nome=grupo['nome'],
                grupo_ordem=grupo['ordem'],
                item_ordem=item['ordem'],
                item_descricao=item['descricao'],
                item_peso_percentual=Decimal(item['peso_percentual']),
                item_observacoes_padrao=item.get('observacoes_padrao', ''),
            )
    competencia.formulario_avaliacao_snapshot = snapshot
    competencia.save(update_fields=['formulario_avaliacao_snapshot', 'atualizado_em'])
    return avaliacao


def gerar_competencias_contrato_v2(contrato):
    """Gera competências mensais da vigência inicial usando checklist ativo e avaliação opcional."""

    from .models import CompetenciaPagamentoV2

    modelo = contrato.checklist_ativo
    if modelo is None:
        raise ValidationError('Cadastre e ative ao menos uma versão de checklist antes de gerar as competências.')

    data_fim = inclusive_end_date(contrato.data_inicio_vigencia, contrato.prazo_inicial_meses)
    periodos = iterar_periodos_competencia(contrato.data_inicio_vigencia, data_fim)
    formulario_ativo = contrato.formulario_avaliacao_ativo

    for periodo_inicio, periodo_fim in periodos:
        competencia, criada = CompetenciaPagamentoV2.objects.get_or_create(
            contrato=contrato,
            periodo_inicio=periodo_inicio,
            periodo_fim=periodo_fim,
            defaults={
                'valor_previsto': contrato.base_mensal,
                'checklist_modelo_snapshot': _snapshot_checklist_modelo(modelo),
                'formulario_avaliacao_snapshot': _snapshot_formulario_avaliacao(formulario_ativo) if formulario_ativo else {},
            },
        )
        if criada:
            atualizar_checklist_snapshot_competencia_v2(competencia, modelo)
            if formulario_ativo:
                criar_avaliacao_shell_competencia_v2(competencia, formulario_ativo)


def recalcular_avaliacao_v2(avaliacao):
    """Atualiza nota final e percentuais sugeridos a partir das respostas lançadas."""

    max_nota = avaliacao.maior_nota_escala
    del max_nota
    respostas = list(avaliacao.itens.order_by('grupo_ordem', 'item_ordem', 'id'))
    soma_pesos_itens = sum((resposta.item_peso_percentual or ZERO) for resposta in respostas) or Decimal('1.00')
    acumulado = ZERO
    for resposta in respostas:
        acumulado += (resposta.nota_valor or ZERO) * ((resposta.item_peso_percentual or ZERO) / soma_pesos_itens)

    nota_final = quantize_money(acumulado) if respostas else ZERO
    percentual = Decimal('100.00')
    for faixa in avaliacao.faixas_liberacao_snapshot:
        nota_minima = Decimal(faixa['nota_minima'])
        nota_maxima = Decimal(faixa['nota_maxima']) if faixa.get('nota_maxima') not in {'', None} else None
        if nota_final < nota_minima:
            continue
        if nota_maxima is not None and nota_final > nota_maxima:
            continue
        percentual = Decimal(faixa['percentual_liberacao'])
        break

    avaliacao.nota_final = nota_final
    avaliacao.percentual_liberacao_sugerido = percentual
    avaliacao.valor_liberado_sugerido = quantize_money((avaliacao.competencia.valor_medido or ZERO) * (percentual / Decimal('100.00')))
    avaliacao.save(
        update_fields=[
            'nota_final',
            'percentual_liberacao_sugerido',
            'valor_liberado_sugerido',
            'atualizado_em',
        ]
    )
    recalcular_competencia_v2(avaliacao.competencia)


def avaliacao_v2_esta_concluida(avaliacao):
    """Só conclui a avaliação quando todos os itens exigidos estiverem completos para fiscal e gestor."""

    respostas = list(avaliacao.itens.order_by('grupo_ordem', 'item_ordem', 'id'))
    if not respostas:
        return False

    max_nota = avaliacao.maior_nota_escala
    for resposta in respostas:
        if resposta.nota_valor is None:
            return False
        if resposta.nota_valor < max_nota:
            if not (resposta.justificativa_fiscal or '').strip():
                return False
            if not (resposta.manifestacao_gestor_item or '').strip():
                return False
    return True


def recalcular_competencia_v2(competencia):
    """Consolida situação, datas de etapa e valores da competência."""

    from django.db.models import Sum

    total_medido = competencia.medicoes.aggregate(total=Sum('valor_subtotal')).get('total') or ZERO
    competencia.valor_medido = quantize_money(total_medido)

    checklist_pendente = competencia.checklist_itens.filter(obrigatorio=True, concluido=False).exists()
    todos_checklist_ok = competencia.checklist_itens.exists() and not checklist_pendente
    competencia.checklist_concluido_em = timezone.now() if todos_checklist_ok else None

    avaliacao = competencia.avaliacao_qualidade_segura
    if avaliacao:
        competencia.valor_liberado_sugerido = avaliacao.valor_liberado_sugerido
    else:
        competencia.valor_liberado_sugerido = competencia.valor_medido

    if competencia_v2_esta_fechada(competencia):
        competencia.save(
            update_fields=[
                'valor_medido',
                'valor_liberado_sugerido',
                'checklist_concluido_em',
                'atualizado_em',
            ]
        )
        return

    if not competencia.checklist_itens.exists():
        competencia.status = competencia.Status.BLOQUEADA
    elif checklist_pendente:
        competencia.status = competencia.Status.CHECKLIST_PENDENTE
    elif not competencia.medicao_concluida_em:
        competencia.status = competencia.Status.MEDICAO_PENDENTE
    elif competencia_v2_exige_avaliacao(competencia) and not (avaliacao and avaliacao.concluida_em):
        competencia.status = competencia.Status.AVALIACAO_PENDENTE
    else:
        competencia.status = competencia.Status.PAGAMENTO_PENDENTE

    competencia.save(
        update_fields=[
            'status',
            'valor_medido',
            'valor_liberado_sugerido',
            'checklist_concluido_em',
            'atualizado_em',
        ]
    )


def validar_fluxo_pagamento_v2(competencia):
    """Confirma se a competência já superou as etapas anteriores ao pagamento."""

    if competencia.status != competencia.Status.PAGAMENTO_PENDENTE:
        raise ValidationError('A competência ainda não está apta para pagamento.')
