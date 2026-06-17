# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Centralizar regras do fluxo de checklist, competências, medição, avaliação e pagamento do Contratos V2.

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone


import calendar
from datetime import date, timedelta
import re

CONTRATO_NUMERO_RE = re.compile(r'^(?P<sequencial>\d{3})/(?P<ano>\d{4})$')

def quantize_money(value):
    from decimal import Decimal, ROUND_HALF_UP
    return (value or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def add_months(base_date, months):
    if not base_date:
        return None
    month_index = base_date.month - 1 + int(months or 0)
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(base_date.day, last_day)
    return date(year, month, day)

def inclusive_end_date(start_date, months):
    final_date = add_months(start_date, months)
    if not final_date:
        return None
    return final_date - timedelta(days=1)

def ultimo_dia_mes(data_referencia):
    return date(
        data_referencia.year,
        data_referencia.month,
        calendar.monthrange(data_referencia.year, data_referencia.month)[1],
    )

def iterar_periodos_competencia(data_inicio, data_fim):
    if not data_inicio or not data_fim or data_fim < data_inicio:
        return []

    periodos = []
    cursor = data_inicio
    while cursor <= data_fim:
        fim_mes = ultimo_dia_mes(cursor)
        periodo_fim = min(fim_mes, data_fim)
        periodos.append((cursor, periodo_fim))
        cursor = periodo_fim + timedelta(days=1)
    return periodos

def parse_numero_contrato(value):
    match = CONTRATO_NUMERO_RE.match((value or '').strip())
    if not match:
        return None
    return int(match.group('sequencial')), int(match.group('ano'))



ZERO = Decimal('0.00')


def validar_processos_sei_contrato(contrato):
    """Bloqueia o fluxo mensal enquanto o contrato não tiver os dois processos SEI completos."""

    campos_faltantes = []
    if not (contrato.processo_sei_gestao_numero or '').strip():
        campos_faltantes.append('Processo SEI (Gestão) - número')
    if not (contrato.processo_sei_gestao_url or '').strip():
        campos_faltantes.append('Processo SEI (Gestão) - link')
    if not (contrato.processo_sei_execucao_numero or '').strip():
        campos_faltantes.append('Processo SEI (Execução) - número')
    if not (contrato.processo_sei_execucao_url or '').strip():
        campos_faltantes.append('Processo SEI (Execução) - link')
    if campos_faltantes:
        raise ValidationError(
            'Preencha os campos obrigatórios de processos SEI antes de gerar competências: '
            + ', '.join(campos_faltantes)
            + '.'
        )


def usuario_eh_admin_sistema(user):
    """Considera como administradores operadores com privilégios globais do portal."""

    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def usuario_pode_gerir_contrato_v2(user, contrato):
    """Gestor, criador do contrato e administradores podem gerir cadastros e autorizações."""

    return bool(
        user
        and user.is_authenticated
        and (
            usuario_eh_admin_sistema(user)
            or user.pk == contrato.gestor_contrato_id
            # O criador do contrato mantém autonomia operacional mesmo quando o gestor ainda não foi definido.
            or user.pk == contrato.criado_por_id
        )
    )


def usuario_pode_gerir_documento_importante_contrato(user, contrato):
    """Define quem pode gerenciar ao menos um documento importante no escopo do contrato."""

    return bool(
        user
        and user.is_authenticated
        and (
            usuario_eh_admin_sistema(user)
            or user.pk == contrato.gestor_contrato_id
            or user.pk == contrato.criado_por_id
        )
    )


def usuario_pode_gerir_documento_importante(user, documento):
    """Permite gestão por administrador, gestor, criador do contrato ou autor do documento."""

    contrato = documento.contrato
    return bool(
        user
        and user.is_authenticated
        and (
            usuario_eh_admin_sistema(user)
            or user.pk == contrato.gestor_contrato_id
            or user.pk == contrato.criado_por_id
            or user.pk == documento.criado_por_id
        )
    )


def usuario_eh_criador_contrato(user, contrato):
    """Retorna se o usuário autenticado é o responsável original pelo cadastro do contrato."""

    return bool(user and user.is_authenticated and user.pk == contrato.criado_por_id)


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


def usuario_pode_preencher_avaliacao_fiscal_v2(user, contrato):
    """Fiscais preenchem a parte fiscal; sem fiscais definidos, o criador cobre o papel inicial."""

    return bool(
        user
        and user.is_authenticated
        and (
            usuario_eh_admin_sistema(user)
            or user.pk == contrato.fiscal_administrativo_id
            or user.pk == contrato.fiscal_tecnico_id
            # Enquanto o contrato ainda nasce sem fiscais, o criador mantém o fluxo operacional destravado.
            or (
                usuario_eh_criador_contrato(user, contrato)
                and not contrato.fiscal_administrativo_id
                and not contrato.fiscal_tecnico_id
            )
        )
    )


def usuario_pode_preencher_avaliacao_gestor_v2(user, contrato):
    """Gestor preenche sua etapa; sem gestor definido, o criador cobre o papel inicial."""

    return bool(
        user
        and user.is_authenticated
        and (
            usuario_eh_admin_sistema(user)
            or user.pk == contrato.gestor_contrato_id
            # O criador atua como responsável transitório até a definição formal do gestor.
            or (usuario_eh_criador_contrato(user, contrato) and not contrato.gestor_contrato_id)
        )
    )


def usuario_pode_preencher_medicao_v2(user, contrato):
    """Nesta primeira fase a medição fica com gestor e administradores."""

    return usuario_pode_gerir_contrato_v2(user, contrato)


def competencia_v2_esta_fechada(competencia):
    """Competências pagas ou canceladas ficam congeladas."""

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

    from .models import ChecklistCompetenciaItem

    validar_competencia_v2_editavel(competencia)
    competencia.checklist_modelo_snapshot = _snapshot_checklist_modelo(modelo)
    competencia.save(update_fields=['checklist_modelo_snapshot', 'atualizado_em'])
    competencia.checklist_itens.all().delete()
    for item_snapshot in competencia.checklist_modelo_snapshot.get('itens', []):
        ChecklistCompetenciaItem.objects.create(
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

    from .models import AvaliacaoCompetenciaItemRespostaV2, AvaliacaoQualidadeCompetencia

    if competencia.avaliacao_qualidade_segura is not None:
        return competencia.avaliacao_qualidade_segura

    snapshot = _snapshot_formulario_avaliacao(formulario)
    avaliacao = AvaliacaoQualidadeCompetencia.objects.create(
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

    from .models import CompetenciaPagamento

    validar_processos_sei_contrato(contrato)

    modelo = contrato.checklist_ativo
    if modelo is None:
        raise ValidationError('Cadastre e ative ao menos uma versão de checklist antes de gerar as competências.')

    data_fim = inclusive_end_date(contrato.data_inicio_vigencia, contrato.prazo_inicial_meses)
    periodos = iterar_periodos_competencia(contrato.data_inicio_vigencia, data_fim)
    formulario_ativo = contrato.formulario_avaliacao_ativo

    for periodo_inicio, periodo_fim in periodos:
        competencia, criada = CompetenciaPagamento.objects.get_or_create(
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
    """Atualiza nota final e percentuais sugeridos a partir da média ponderada dos itens."""

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
    """Só conclui a avaliação quando conteúdo e PDF assinado estiverem fechados."""

    respostas = list(avaliacao.itens.order_by('grupo_ordem', 'item_ordem', 'id'))
    if not respostas:
        return False

    max_nota = avaliacao.maior_nota_escala
    for resposta in respostas:
        # A nota final que vale continua sendo a do gestor quando existir,
        # mas a conclusão precisa respeitar as obrigações de cada papel separadamente.
        if resposta.nota_fiscal_valor is None:
            return False
        if resposta.nota_gestor_valor is None:
            return False
        if resposta.nota_fiscal_valor < max_nota and not (resposta.justificativa_fiscal or '').strip():
            return False
        if resposta.nota_gestor_valor < max_nota and not (resposta.manifestacao_gestor_item or '').strip():
            return False
    # O fechamento da etapa depende do relatório assinado ter voltado para a competência.
    return bool(avaliacao.competencia.avaliacao_assinada)


def competencia_medicao_v2_esta_concluida(competencia):
    """Define a conclusão da medição expandida com aceites e dados financeiros."""

    possui_medicoes = competencia.medicoes.filter(quantidade__gt=0).exists()
    possui_nf_principal = bool(competencia.nota_fiscal_fatura and (competencia.numero_nota_fiscal or '').strip())
    possui_aceite_provisorio = bool(
        competencia.aceite_provisorio_arquivo and competencia.data_aceite_provisorio and competencia.prazo_aceite_definitivo_dias
    )
    possui_aceite_definitivo = bool(
        competencia.aceite_definitivo_arquivo and competencia.data_aceite_definitivo and competencia.prazo_pagamento_dias
    )
    if not (possui_medicoes and possui_nf_principal and possui_aceite_provisorio and possui_aceite_definitivo):
        return False
    if competencia.nota_adicional_nao_consta:
        return True
    if competencia.possui_nota_adicional:
        return bool(
            competencia.nota_adicional_arquivo
            and (competencia.numero_nota_adicional or '').strip()
            and (competencia.valor_nota_adicional or ZERO) >= ZERO
        )
    return False


def competencia_checklist_v2_esta_concluido(competencia):
    """Agrupa checklist oficial e checklist adicional em uma única checagem operacional."""

    itens = competencia.checklist_itens.all()
    return bool(itens.exists() and not itens.filter(obrigatorio=True, concluido=False).exists())


def recalcular_competencia_v2(competencia):
    """Consolida situação, datas de etapa e valores da competência."""

    from django.db.models import Sum

    total_medido = competencia.medicoes.aggregate(total=Sum('valor_subtotal')).get('total') or ZERO
    competencia.valor_medido = quantize_money(total_medido)

    checklist_pendente = competencia.checklist_itens.filter(obrigatorio=True, concluido=False).exists()
    todos_checklist_ok = competencia_checklist_v2_esta_concluido(competencia)
    competencia.checklist_concluido_em = timezone.now() if todos_checklist_ok else None
    medicao_concluida = competencia_medicao_v2_esta_concluida(competencia)
    if medicao_concluida and not competencia.medicao_concluida_em:
        competencia.medicao_concluida_em = timezone.now()
    elif not medicao_concluida:
        competencia.medicao_concluida_em = None

    avaliacao = competencia.avaliacao_qualidade_segura
    if avaliacao:
        competencia.valor_liberado_sugerido = avaliacao.valor_liberado_sugerido
    else:
        competencia.valor_liberado_sugerido = competencia.valor_medido
    competencia.valor_liberado_final = quantize_money((competencia.valor_nota_fiscal or ZERO) - competencia.total_retencoes)
    competencia.valor_liquido_nota_adicional = quantize_money((competencia.valor_nota_adicional or ZERO) - competencia.total_retencoes_adicionais)

    if competencia_v2_esta_fechada(competencia):
        competencia.save(
            update_fields=[
                'valor_medido',
                'valor_liberado_sugerido',
                'valor_liberado_final',
                'valor_liquido_nota_adicional',
                'checklist_concluido_em',
                'medicao_concluida_em',
                'atualizado_em',
            ]
        )
        return

    if not competencia.checklist_itens.exists():
        competencia.status = competencia.Status.BLOQUEADA
    elif not medicao_concluida:
        competencia.status = competencia.Status.MEDICAO_PENDENTE
    elif competencia_v2_exige_avaliacao(competencia) and not (avaliacao and avaliacao.concluida_em):
        competencia.status = competencia.Status.AVALIACAO_PENDENTE
    elif checklist_pendente:
        competencia.status = competencia.Status.CHECKLIST_PENDENTE
    elif not competencia.download_realizado_em:
        competencia.status = competencia.Status.DOWNLOAD_PENDENTE
    elif not (competencia.ordem_bancaria_arquivo and competencia.data_pagamento):
        competencia.status = competencia.Status.OB_PENDENTE
    else:
        competencia.status = competencia.Status.PAGA

    competencia.save(
        update_fields=[
            'status',
            'valor_medido',
            'valor_liberado_sugerido',
            'valor_liberado_final',
            'valor_liquido_nota_adicional',
            'checklist_concluido_em',
            'medicao_concluida_em',
            'atualizado_em',
        ]
    )


def validar_fluxo_pagamento_v2(competencia):
    """Mantém compatibilidade: agora valida a liberação da etapa final de OB."""

    if competencia.status != competencia.Status.OB_PENDENTE:
        raise ValidationError('A competência ainda não está apta para anexar a ordem bancária.')


def enviar_alertas_monitoramento_competencias(referencia=None):
    """Dispara alertas automáticos de 50% e de 75%+ para competências em monitoramento."""

    from mensageria_assincrona.models import Mensagem
    from mensageria_assincrona.services import criar_mensagem_rascunho, publicar_mensagem

    hoje = referencia or timezone.localdate()
    enviados = 0
    competencias = (
        __import__('contratos.models', fromlist=['CompetenciaPagamento']).CompetenciaPagamento.objects
        .select_related('contrato')
        .filter(monitoramento_etapa__gt='', monitoramento_inicio__isnull=False, monitoramento_limite__isnull=False)
        .exclude(status__in=['PAGA', 'CANCELADA'])
    )
    for competencia in competencias:
        percentual = competencia.monitoramento_percentual
        deve_enviar = False
        if percentual >= 75:
            deve_enviar = competencia.alerta_75_ultimo_envio_em != hoje
        elif percentual >= 50:
            deve_enviar = competencia.alerta_50_enviado_em != hoje
        if not deve_enviar:
            continue

        destinatarios = [
            usuario
            for usuario in [
                competencia.contrato.fiscal_administrativo,
                competencia.contrato.fiscal_tecnico,
                competencia.contrato.gestor_contrato,
                competencia.contrato.criado_por,
            ]
            if usuario and usuario.is_active
        ]
        if not destinatarios:
            continue

        dias_restantes = max((competencia.monitoramento_limite - hoje).days, 0)
        mensagem = criar_mensagem_rascunho(
            assunto=f'Prazo monitorado: {competencia.monitoramento_etapa}',
            corpo=(
                f'Etapa pendente: {competencia.monitoramento_etapa}\n'
                f'Contrato: {competencia.contrato.numero_contrato}\n'
                f'Competência: {competencia.periodo_inicio:%m/%Y}\n'
                f'Data limite: {competencia.monitoramento_limite:%d/%m/%Y}\n'
                f'Dias restantes: {dias_restantes}'
            ),
            prioridade=Mensagem.Prioridade.ALTA if percentual >= 75 else Mensagem.Prioridade.NORMAL,
        )
        mensagem.origem_tipo = Mensagem.OrigemTipo.SISTEMA
        mensagem.origem_app = 'contratos'
        mensagem.origem_model = 'CompetenciaPagamento'
        mensagem.origem_pk = f'{competencia.pk}:{competencia.monitoramento_etapa}:{hoje.isoformat()}'
        mensagem.save(update_fields=['origem_tipo', 'origem_app', 'origem_model', 'origem_pk', 'updated_at'])
        mensagem.usuarios_alvo.add(*destinatarios)
        publicar_mensagem(mensagem, publicada_em=timezone.now())
        if percentual >= 75:
            competencia.alerta_75_ultimo_envio_em = hoje
        else:
            competencia.alerta_50_enviado_em = hoje
        competencia.save(update_fields=['alerta_50_enviado_em', 'alerta_75_ultimo_envio_em', 'atualizado_em'])
        enviados += 1
    return enviados
