from collections import defaultdict
from decimal import Decimal
from html import escape
import re

from django.db import transaction
from django.db.models import Max

from .models import DfdItemTabela, EtpTic, ItemTR, SessaoTR, TabelaItemLinha, TermoReferencia


ETP_TIC_SECOES = [
    {'numero': 1, 'titulo': 'Informacoes Basicas', 'descricao': '', 'campos': ['numero_processo', 'nome', 'link']},
    {'numero': 2, 'titulo': 'Descricao da Necessidade', 'descricao': 'Descricao da necessidade que a contratacao pretende atender.', 'campos': ['descricao_necessidade']},
    {'numero': 3, 'titulo': 'Area Requisitante', 'descricao': '', 'campos': ['area_requisitante', 'responsavel_area']},
    {'numero': 4, 'titulo': 'Necessidades de Negocio', 'descricao': 'Defina as necessidades de negocio que a contratacao visa atender.', 'campos': ['necessidades_negocio']},
    {'numero': 5, 'titulo': 'Necessidades Tecnologicas', 'descricao': 'Defina as necessidades tecnologicas relacionadas a solucao.', 'campos': ['necessidades_tecnologicas']},
    {'numero': 6, 'titulo': 'Demais Requisitos Necessarios e Suficientes', 'descricao': 'Descreva requisitos indispensaveis ao atendimento da necessidade.', 'campos': ['demais_requisitos']},
    {'numero': 7, 'titulo': 'Estimativa da Demanda', 'descricao': 'Detalhe o quantitativo de bens e servicos.', 'campos': ['estimativa_demanda']},
    {'numero': 8, 'titulo': 'Levantamento de Solucoes', 'descricao': 'Registre solucoes disponiveis para atender a necessidade.', 'campos': ['levantamento_solucoes']},
    {'numero': 9, 'titulo': 'Analise Comparativa de Solucoes', 'descricao': 'Compare solucoes sob criterios tecnicos, funcionais e economicos.', 'campos': ['analise_comparativa_solucoes']},
    {'numero': 10, 'titulo': 'Registro de Solucoes Inviaveis', 'descricao': 'Registre solucoes consideradas inviaveis.', 'campos': ['solucoes_inviaveis']},
    {'numero': 11, 'titulo': 'Analise Comparativa de Custos (TCO)', 'descricao': 'Compare custos totais de propriedade das solucoes viaveis.', 'campos': ['analise_comparativa_custos_tco']},
    {'numero': 12, 'titulo': 'Descricao da Solucao de TIC', 'descricao': 'Identifique a solucao escolhida para contratacao.', 'campos': ['descricao_solucao_tic']},
    {'numero': 13, 'titulo': 'Estimativa de Custo Total', 'descricao': 'Registre valor estimado e memoria da estimativa.', 'campos': ['estimativa_custo_valor', 'estimativa_custo_texto']},
    {'numero': 14, 'titulo': 'Justificativa técnica da escolha da solução', 'descricao': 'Descreva as razoes tecnicas da escolha da solucao.', 'campos': ['justificativa_tecnica']},
    {'numero': 15, 'titulo': 'Justificativa econômica da escolha da solução', 'descricao': 'Descreva as razoes economicas da escolha da solucao.', 'campos': ['justificativa_economica']},
    {'numero': 16, 'titulo': 'Benefícios a serem alcançados com a contratação', 'descricao': 'Identifique resultados e beneficios esperados.', 'campos': ['beneficios_contratacao']},
    {'numero': 17, 'titulo': 'Providencias a Serem Adotadas', 'descricao': 'Informe providencias ou adequacoes necessarias.', 'campos': ['providencias_adotadas']},
    {'numero': 18, 'titulo': 'Declaracao de Viabilidade', 'descricao': '', 'campos': ['declaracao_viabilidade', 'justificativa_viabilidade']},
]
ETP_TIC_SECOES_MAP = {secao['numero']: secao for secao in ETP_TIC_SECOES}

DFD_SECOES = [
    {
        'numero': 1,
        'titulo': 'Informacoes Preliminares',
        'descricao': '',
        'campos': ['informacoes_preliminares'],
        'numerar': False,
    },
    {
        'numero': 2,
        'numero_documento': 1,
        'titulo': 'Descricao Sucinta do Objeto',
        'descricao': 'Descreva o objeto e cadastre os itens da tabela quando houver.',
        'campos': ['descricao_objeto'],
        'numerar': True,
    },
    {
        'numero': 3,
        'numero_documento': 2,
        'titulo': 'Justificativa da Necessidade',
        'descricao': '',
        'campos': ['justificativa_necessidade'],
        'numerar': True,
    },
    {
        'numero': 4,
        'numero_documento': 3,
        'titulo': 'Estimativa de Quantidade e Valores',
        'descricao': '',
        'campos': ['estimativa_quantidade_valores'],
        'numerar': True,
    },
    {
        'numero': 5,
        'numero_documento': 4,
        'titulo': 'Vinculacao com outro DFD',
        'descricao': '',
        'campos': ['vinculacao_outro_dfd'],
        'numerar': True,
    },
    {
        'numero': 6,
        'titulo': 'Responsaveis',
        'descricao': '',
        'campos': ['responsaveis'],
        'numerar': False,
    },
]
DFD_SECOES_MAP = {secao['numero']: secao for secao in DFD_SECOES}


def split_paragraphs(texto):
    blocos = re.split(r'\n\s*\n', (texto or '').strip())
    return [bloco.strip() for bloco in blocos if bloco.strip()]


def etp_secao_preenchida(etp, numero):
    for campo in ETP_TIC_SECOES_MAP[numero]['campos']:
        valor = getattr(etp, campo, None)
        if isinstance(valor, str) and valor.strip():
            return True
        if valor not in (None, '', Decimal('0')):
            return True
    return False


def etp_status_por_secao(etp):
    status = {}
    for secao in ETP_TIC_SECOES:
        numero = secao['numero']
        preenchida = etp_secao_preenchida(etp, numero)
        if numero < etp.secao_atual:
            status[numero] = 'concluido' if preenchida else 'nao-iniciado'
        elif numero == etp.secao_atual:
            status[numero] = 'em-andamento' if preenchida else 'nao-iniciado'
        else:
            status[numero] = 'nao-iniciado'
    return status


def dfd_secao_preenchida(dfd, numero):
    secao = DFD_SECOES_MAP[numero]
    for campo in secao['campos']:
        valor = getattr(dfd, campo, None)
        if isinstance(valor, str) and valor.strip():
            return True
        if valor not in (None, ''):
            return True
    if numero == 2 and dfd.pk and dfd.itens_tabela.exists():
        return True
    return False


def dfd_status_por_secao(dfd):
    status = {}
    for secao in DFD_SECOES:
        numero = secao['numero']
        preenchida = dfd_secao_preenchida(dfd, numero)
        if numero < dfd.secao_atual:
            status[numero] = 'concluido' if preenchida else 'nao-iniciado'
        elif numero == dfd.secao_atual:
            status[numero] = 'em-andamento' if preenchida else 'nao-iniciado'
        else:
            status[numero] = 'nao-iniciado'
    return status


def render_etp_sections(etp):
    secoes = []
    for secao in ETP_TIC_SECOES:
        numero = secao['numero']
        entradas = []
        if numero == 1:
            if etp.numero_processo:
                entradas.append(f'{numero}.1. Numero do processo: {etp.numero_processo}')
            if etp.nome:
                entradas.append(f'{numero}.2. Nome: {etp.nome}')
            if etp.link:
                entradas.append(f'{numero}.3. Link: {etp.link}')
        elif numero == 3:
            if etp.area_requisitante:
                entradas.append(f'{numero}.1. Area requisitante: {etp.area_requisitante}')
            if etp.responsavel_area:
                entradas.append(f'{numero}.2. Responsavel: {etp.responsavel_area}')
        elif numero == 13:
            if etp.estimativa_custo_valor is not None:
                entradas.append(f'{numero}.1. Valor estimado: R$ {etp.estimativa_custo_valor}')
                start = 2
            else:
                start = 1
            for idx, paragrafo in enumerate(split_paragraphs(etp.estimativa_custo_texto), start=start):
                entradas.append(f'{numero}.{idx}. {paragrafo}')
        elif numero == 18:
            if etp.declaracao_viabilidade:
                entradas.append(f'{numero}.1. {etp.declaracao_viabilidade.strip()}')
            for idx, paragrafo in enumerate(split_paragraphs(etp.justificativa_viabilidade), start=2):
                entradas.append(f'{numero}.{idx}. {paragrafo}')
        else:
            campo = secao['campos'][0]
            for idx, paragrafo in enumerate(split_paragraphs(getattr(etp, campo, '')), start=1):
                entradas.append(f'{numero}.{idx}. {paragrafo}')
        secoes.append({**secao, 'entradas': entradas})
    return secoes


def render_dfd_sections(dfd):
    secoes = []
    tabela = list(DfdItemTabela.objects.filter(dfd=dfd).order_by('ordem', 'id')) if dfd.pk else []
    for secao in DFD_SECOES:
        entradas = []
        campo = secao['campos'][0]
        texto = getattr(dfd, campo, '')
        if secao['numerar']:
            numero_documento = secao['numero_documento']
            for idx, paragrafo in enumerate(split_paragraphs(texto), start=1):
                entradas.append(f'{numero_documento}.{idx}. {paragrafo}')
        else:
            entradas = split_paragraphs(texto)
        secoes.append({**secao, 'entradas': entradas, 'tabela': tabela if secao['numero'] == 2 else []})
    return secoes


def next_ordem_sessao(termo):
    return (termo.sessoes.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1


def next_ordem_item(sessao, parent):
    parent_id = parent.id if parent else None
    return (sessao.itens.filter(parent_id=parent_id).aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1


def normalize_sessoes(termo):
    for idx, sessao in enumerate(termo.sessoes.order_by('ordem', 'id'), start=1):
        if sessao.ordem != idx:
            sessao.ordem = idx
            sessao.save(update_fields=['ordem'])


def normalize_items(sessao, parent_id):
    for idx, item in enumerate(sessao.itens.filter(parent_id=parent_id).order_by('ordem', 'id'), start=1):
        if item.ordem != idx:
            item.ordem = idx
            item.save(update_fields=['ordem'])


def int_to_roman(num):
    pairs = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]
    out = []
    for val, sym in pairs:
        while num >= val:
            out.append(sym)
            num -= val
    return ''.join(out)


def sibling_index(item, siblings):
    idx = 0
    for sibling in siblings:
        if sibling.tipo == item.tipo:
            idx += 1
        elif item.tipo != ItemTR.Tipo.NUMERICO:
            idx = 0
        if sibling.id == item.id:
            return idx
    return 1


def item_parent_for_tipo(parent, tipo):
    if parent and tipo == ItemTR.Tipo.INCISO and parent.tipo == ItemTR.Tipo.INCISO:
        return parent.parent
    return parent


def enum_prefix(item, siblings):
    idx = sibling_index(item, siblings)
    if item.tipo == ItemTR.Tipo.INCISO:
        return f'{int_to_roman(idx)})'
    if item.tipo == ItemTR.Tipo.ALINEA:
        return f'{chr(ord("a") + idx - 1)})'
    return ''


def quantidade_text(value):
    if value is None:
        return ''
    text = f'{value}'.replace('.', ',')
    return text[:-3] if text.endswith(',00') else text


def red_mark_segments(text):
    text = text or ''
    segments = []
    buffer = []
    index = 0

    def flush_buffer():
        if buffer:
            segments.append((''.join(buffer), False))
            buffer.clear()

    while index < len(text):
        char = text[index]
        if char != '*':
            buffer.append(char)
            index += 1
            continue

        end = text.find('*', index + 1)
        if end > index + 1:
            flush_buffer()
            segments.append((text[index + 1:end], True))
            index = end + 1
            continue

        match = re.match(r'\*([^\s*]+)', text[index:])
        if match:
            flush_buffer()
            segments.append((match.group(1), True))
            index += len(match.group(0))
            continue

        buffer.append(char)
        index += 1

    flush_buffer()
    return segments


def red_marked_html(text):
    parts = []
    for segment, is_red in red_mark_segments(text):
        value = escape(segment).replace('\n', '<br>')
        if is_red:
            parts.append(f'<span class="text-danger">{value}</span>')
        else:
            parts.append(value)
    return ''.join(parts)


def build_item_rows(sessao):
    itens = list(sessao.itens.select_related('parent').order_by('parent_id', 'ordem', 'id'))
    by_parent = defaultdict(list)
    for item in itens:
        by_parent[item.parent_id].append(item)
    rows = []

    def walk(parent_id, parent_index, depth):
        siblings = by_parent.get(parent_id, [])
        for item in siblings:
            idx = sibling_index(item, siblings)
            indice = parent_index if item.tipo != ItemTR.Tipo.NUMERICO else f'{parent_index}.{idx}'
            rows.append({
                'item': item,
                'indice': indice,
                'enum_prefix': enum_prefix(item, siblings),
                'pode_tabela_itens': indice == '1.1',
                'depth': depth,
                'indent': depth * 1.5,
            })
            child_parent_index = indice if item.tipo == ItemTR.Tipo.NUMERICO else parent_index
            walk(item.id, child_parent_index, depth + 1)

    walk(None, str(sessao.ordem), 0)
    return rows


def build_termo_tree(termo):
    tabela_linhas = (
        TabelaItemLinha.objects.filter(item__sessao__termo=termo)
        .select_related('item')
        .order_by('item_id', 'ordem', 'id')
    )
    tabela_por_item = defaultdict(list)
    for linha in tabela_linhas:
        tabela_por_item[linha.item_id].append(linha)

    tree = []
    for sessao in termo.sessoes.all():
        rows = build_item_rows(sessao)
        for row in rows:
            row['tabela_linhas'] = tabela_por_item.get(row['item'].id, [])
        tree.append({'sessao': sessao, 'rows': rows})
    return tree


def item_descendant_ids(item):
    ids = set()
    stack = list(item.filhos.all())
    while stack:
        child = stack.pop()
        ids.add(child.id)
        stack.extend(list(child.filhos.all()))
    return ids


def _insert_at_position(siblings, item, position):
    ordered = list(siblings)
    if position:
        index = max(0, min(position - 1, len(ordered)))
        ordered.insert(index, item)
    else:
        ordered.append(item)
    return ordered


def move_item(item, target, action, target_sessao=None, child_position=None):
    if action not in {'after', 'child'}:
        raise ValueError('Acao de movimentacao invalida.')
    if target and target.id == item.id:
        raise ValueError('Nao e possivel mover um item para ele mesmo.')
    if target and target.id in item_descendant_ids(item):
        raise ValueError('Nao e possivel mover um item para dentro de um descendente.')

    old_sessao = item.sessao
    old_parent_id = item.parent_id

    with transaction.atomic():
        item = ItemTR.objects.select_for_update().get(pk=item.pk)
        if action == 'child' and target:
            new_sessao = target.sessao
            new_parent = target
            siblings = list(new_sessao.itens.filter(parent=new_parent).exclude(pk=item.pk).order_by('ordem', 'id'))
            ordered = _insert_at_position(siblings, item, child_position)
            new_ordem = 1
        elif target:
            new_sessao = target.sessao
            new_parent = target.parent
            siblings = list(new_sessao.itens.filter(parent=new_parent).exclude(pk=item.pk).order_by('ordem', 'id'))
            ordered = []
            inserted = False
            for sibling in siblings:
                ordered.append(sibling)
                if sibling.id == target.id:
                    ordered.append(item)
                    inserted = True
            if not inserted:
                ordered.append(item)
            new_ordem = 1
        else:
            new_sessao = target_sessao
            new_parent = None
            siblings = list(new_sessao.itens.filter(parent=None).exclude(pk=item.pk).order_by('ordem', 'id'))
            ordered = _insert_at_position(siblings, item, child_position)
            new_ordem = 1

        item.sessao = new_sessao
        item.parent = new_parent
        item.ordem = new_ordem
        item.save(update_fields=['sessao', 'parent', 'ordem', 'atualizado_em'])
        _cascade_sessao(item, new_sessao)

        normalize_items(old_sessao, old_parent_id)
        normalize_items(new_sessao, new_parent.id if new_parent else None)
        if action == 'after' and target or action == 'child':
            for idx, sibling in enumerate(ordered, start=1):
                ItemTR.objects.filter(pk=sibling.pk).update(ordem=idx)


def duplicate_item(item, target, action, target_sessao=None, child_position=None):
    if action not in {'after', 'child'}:
        raise ValueError('Acao de duplicacao invalida.')
    if target and target.id == item.id:
        raise ValueError('Nao e possivel duplicar um item para ele mesmo.')
    if target and target.id in item_descendant_ids(item):
        raise ValueError('Nao e possivel duplicar um item para dentro de um descendente.')

    with transaction.atomic():
        item = ItemTR.objects.select_related('sessao', 'parent').get(pk=item.pk)
        if action == 'child' and target:
            new_sessao = target.sessao
            new_parent = target
            new_ordem = 1
            ordered = list(new_sessao.itens.filter(parent=new_parent).order_by('ordem', 'id'))
        elif target:
            new_sessao = target.sessao
            new_parent = target.parent
            new_ordem = 1
            ordered = list(new_sessao.itens.filter(parent=new_parent).order_by('ordem', 'id'))
        else:
            new_sessao = target_sessao
            new_parent = None
            new_ordem = 1
            ordered = list(new_sessao.itens.filter(parent=None).order_by('ordem', 'id'))

        duplicate = _copy_item_tree(item, new_sessao, new_parent, new_ordem)

        if action == 'after' and target:
            reordered = []
            inserted = False
            for sibling in ordered:
                reordered.append(sibling)
                if sibling.id == target.id:
                    reordered.append(duplicate)
                    inserted = True
            if not inserted:
                reordered.append(duplicate)
            for idx, sibling in enumerate(reordered, start=1):
                ItemTR.objects.filter(pk=sibling.pk).update(ordem=idx)
        elif action == 'child':
            reordered = _insert_at_position(ordered, duplicate, child_position)
            for idx, sibling in enumerate(reordered, start=1):
                ItemTR.objects.filter(pk=sibling.pk).update(ordem=idx)
        else:
            normalize_items(new_sessao, new_parent.id if new_parent else None)

        return duplicate


def _copy_item_tree(item, sessao, parent, ordem):
    duplicate = ItemTR.objects.create(
        sessao=sessao,
        parent=parent,
        tipo=item.tipo,
        texto=item.texto,
        ordem=ordem,
    )
    for linha in item.tabela_linhas.order_by('ordem', 'id'):
        TabelaItemLinha.objects.create(
            item=duplicate,
            ordem=linha.ordem,
            descricao=linha.descricao,
            catmat_catser=linha.catmat_catser,
            siafisico=linha.siafisico,
            unidade_fornecimento=linha.unidade_fornecimento,
            quantidade=linha.quantidade,
        )
    for idx, child in enumerate(item.filhos.order_by('ordem', 'id'), start=1):
        _copy_item_tree(child, sessao, duplicate, idx)
    return duplicate


def _cascade_sessao(item, sessao):
    for child in item.filhos.all():
        if child.sessao_id != sessao.id:
            child.sessao = sessao
            child.save(update_fields=['sessao'])
        _cascade_sessao(child, sessao)
