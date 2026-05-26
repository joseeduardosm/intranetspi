from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from html import escape
import re

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    Dfd,
    DfdItemTabela,
    EtpTic,
    ItemEtpTic,
    ItemTR,
    PesquisaPreco,
    PesquisaPrecoFornecedor,
    PesquisaPrecoItemValor,
    SessaoEtpTic,
    SessaoTR,
    TabelaItemLinha,
    TermoReferencia,
)


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
        'rotulo': 'Informacoes Preliminares',
        'descricao': '',
        'campos': ['informacoes_preliminares'],
        'numerar': False,
    },
    {
        'numero': 2,
        'numero_documento': 1,
        'titulo': 'Descricao Sucinta do Objeto',
        'rotulo': '1. Descricao Sucinta do Objeto',
        'descricao': 'Descreva o objeto e cadastre os itens da tabela quando houver.',
        'campos': ['descricao_objeto', 'objeto_nao_luxo'],
        'numerar': True,
    },
    {
        'numero': 3,
        'numero_documento': 2,
        'titulo': 'Justificativa da Necessidade',
        'rotulo': '2. Justificativa da Necessidade',
        'descricao': '',
        'campos': ['justificativa_necessidade'],
        'numerar': True,
    },
    {
        'numero': 4,
        'numero_documento': 3,
        'titulo': 'Estimativa de Quantidade e Valores',
        'rotulo': '3. Estimativa de Quantidade e Valores',
        'descricao': '',
        'campos': ['estimativa_quantidade_valores'],
        'numerar': True,
    },
    {
        'numero': 5,
        'numero_documento': 4,
        'titulo': 'Vinculacao com outro DFD',
        'rotulo': '4. Vinculacao com outro DFD',
        'descricao': '',
        'campos': ['vinculacao_outro_dfd'],
        'numerar': True,
    },
    {
        'numero': 6,
        'titulo': 'Responsaveis',
        'rotulo': 'Responsaveis',
        'descricao': '',
        'campos': ['responsaveis'],
        'numerar': False,
    },
]
DFD_SECOES_MAP = {secao['numero']: secao for secao in DFD_SECOES}


def split_paragraphs(texto):
    blocos = re.split(r'\n\s*\n', (texto or '').strip())
    return [bloco.strip() for bloco in blocos if bloco.strip()]


def format_dfd_item_1_2(texto):
    texto = (texto or Dfd.OBJETO_NAO_LUXO_PADRAO).strip()
    texto = re.sub(r'^\s*(?:item\s*)?1\.2\.?\s*[:.-]?\s*', '', texto, flags=re.IGNORECASE)
    return f'1.2. {texto}' if texto else ''


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
        entradas_apos_tabela = []
        campo = secao['campos'][0]
        texto = getattr(dfd, campo, '')
        if secao['numerar']:
            numero_documento = secao['numero_documento']
            if secao['numero'] == 2:
                paragrafos = split_paragraphs(texto)
                if paragrafos:
                    entradas.append(f'{numero_documento}.1. ' + '\n\n'.join(paragrafos))
                item_1_2 = format_dfd_item_1_2(dfd.objeto_nao_luxo)
                entradas_apos_tabela = [item_1_2] if item_1_2 else []
            else:
                for idx, paragrafo in enumerate(split_paragraphs(texto), start=1):
                    entradas.append(f'{numero_documento}.{idx}. {paragrafo}')
        else:
            entradas = split_paragraphs(texto)
        secoes.append({
            **secao,
            'entradas': entradas,
            'entradas_apos_tabela': entradas_apos_tabela,
            'alinhamento': 'center' if secao['numero'] == 6 else 'left' if secao['numero'] == 1 else 'justify',
            'tabela': tabela if secao['numero'] == 2 else [],
        })
    return secoes


def next_ordem_sessao(termo):
    return (termo.sessoes.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1


def next_ordem_etp_sessao(etp):
    return (etp.sessoes.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1


def next_ordem_item(sessao, parent):
    parent_id = parent.id if parent else None
    return (sessao.itens.filter(parent_id=parent_id).aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1


def next_ordem_etp_item(sessao, parent):
    parent_id = parent.id if parent else None
    return (sessao.itens.filter(parent_id=parent_id).aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1


def normalize_sessoes(termo):
    for idx, sessao in enumerate(termo.sessoes.order_by('ordem', 'id'), start=1):
        if sessao.ordem != idx:
            sessao.ordem = idx
            sessao.save(update_fields=['ordem'])


def normalize_etp_sessoes(etp):
    for idx, sessao in enumerate(etp.sessoes.order_by('ordem', 'id'), start=1):
        if sessao.ordem != idx:
            sessao.ordem = idx
            sessao.save(update_fields=['ordem'])


def normalize_items(sessao, parent_id):
    for idx, item in enumerate(sessao.itens.filter(parent_id=parent_id).order_by('ordem', 'id'), start=1):
        if item.ordem != idx:
            item.ordem = idx
            item.save(update_fields=['ordem'])


def normalize_etp_items(sessao, parent_id):
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
        return f'{int_to_roman(idx)}.'
    if item.tipo == ItemTR.Tipo.ALINEA:
        return f'{chr(ord("a") + idx - 1)})'
    return ''


def etp_sibling_index(item, siblings):
    idx = 0
    for sibling in siblings:
        if sibling.tipo == item.tipo:
            idx += 1
        elif item.tipo != ItemEtpTic.Tipo.NUMERICO:
            idx = 0
        if sibling.id == item.id:
            return idx
    return 1


def etp_enum_prefix(item, siblings):
    if item.tipo == ItemEtpTic.Tipo.INCISO:
        return f'{int_to_roman(etp_sibling_index(item, siblings))}.'
    if item.tipo == ItemEtpTic.Tipo.ALINEA:
        return f'{chr(ord("a") + etp_sibling_index(item, siblings) - 1)})'
    return ''


def parse_bulk_item_markers(texto, max_hash_level=4):
    roots = []
    stack = {}
    current = None
    last_numeric = None
    last_inciso = None

    for raw_line in (texto or '').splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith('@'):
            item_text = line[1:].strip()
            if not item_text:
                continue
            node = {'tipo': 'SUBSECAO', 'texto': item_text, 'filhos': []}
            roots.append(node)
            stack = {}
            current = node
            last_numeric = None
            last_inciso = None
            continue

        if line.startswith('**'):
            item_text = line[2:].strip()
            if not item_text:
                continue
            node = {'tipo': 'INCISO', 'texto': item_text, 'filhos': []}
            if last_numeric is None:
                roots.append(node)
            else:
                last_numeric['filhos'].append(node)
            current = node
            last_inciso = node
            continue

        if line.startswith('$$'):
            item_text = line[2:].strip()
            parent = last_inciso or last_numeric
            if not item_text:
                continue
            node = {'tipo': 'ALINEA', 'texto': item_text, 'filhos': []}
            if parent is None:
                roots.append(node)
            else:
                parent['filhos'].append(node)
            current = node
            continue

        marker_level = 0
        for char in line:
            if char != '#':
                break
            marker_level += 1
        if 1 <= marker_level <= max_hash_level:
            item_text = line[marker_level:].strip()
            if not item_text:
                continue
            node = {'tipo': 'NUMERICO', 'texto': item_text, 'filhos': []}
            parent_level = max((level for level in stack if level < marker_level), default=None)
            if parent_level is None:
                roots.append(node)
            else:
                stack[parent_level]['filhos'].append(node)
            stack = {level: value for level, value in stack.items() if level < marker_level}
            stack[marker_level] = node
            current = node
            last_numeric = node
            last_inciso = None
            continue

        if current:
            current['texto'] = f"{current['texto']}\n{line}"

    return roots


def replace_item_with_marker_nodes(item, nodes, tipo_enum):
    if not nodes:
        return item, 0

    model = item.__class__

    with transaction.atomic():
        item = model.objects.select_for_update().select_related('sessao', 'parent').get(pk=item.pk)
        sessao = item.sessao
        parent = item.parent
        parent_id = item.parent_id
        ordered_siblings = list(sessao.itens.filter(parent_id=parent_id).exclude(pk=item.pk).order_by('ordem', 'id'))
        previous_siblings = [sibling for sibling in ordered_siblings if (sibling.ordem, sibling.id) < (item.ordem, item.id)]
        next_siblings = [sibling for sibling in ordered_siblings if (sibling.ordem, sibling.id) > (item.ordem, item.id)]
        created_count = 0

        def create_children(current_nodes, current_parent):
            nonlocal created_count
            for offset, node in enumerate(current_nodes, start=1):
                child = model.objects.create(
                    sessao=sessao,
                    parent=current_parent,
                    tipo=getattr(tipo_enum, node['tipo']),
                    texto=node['texto'],
                    ordem=offset,
                )
                created_count += 1
                create_children(node['filhos'], child)

        first_node = nodes[0]
        item.filhos.all().delete()
        item.tipo = getattr(tipo_enum, first_node['tipo'])
        item.texto = first_node['texto']
        item.ordem = len(previous_siblings) + 1
        item.save(update_fields=['tipo', 'texto', 'ordem', 'atualizado_em'])
        created_count += 1
        create_children(first_node['filhos'], item)

        new_roots = []
        for node in nodes[1:]:
            root = model.objects.create(
                sessao=sessao,
                parent=parent,
                tipo=getattr(tipo_enum, node['tipo']),
                texto=node['texto'],
                ordem=1,
            )
            created_count += 1
            create_children(node['filhos'], root)
            new_roots.append(root)

        for idx, sibling in enumerate(previous_siblings + [item] + new_roots + next_siblings, start=1):
            model.objects.filter(pk=sibling.pk).update(ordem=idx)

    item.refresh_from_db()
    return item, created_count


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

        marker = '**' if text.startswith('**', index) else '*'
        marker_len = len(marker)
        content_start = index + marker_len
        paragraph_break = text.find('\n\n', content_start)
        end = text.find(marker, content_start)
        closes_in_same_paragraph = end > content_start and (paragraph_break == -1 or end < paragraph_break)

        if closes_in_same_paragraph:
            flush_buffer()
            segments.append((text[content_start:end], True))
            index = end + marker_len
            continue

        match = re.match(r'\*{1,2}([^\s*]+)', text[index:])
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
            is_subsecao = item.tipo == ItemTR.Tipo.SUBSECAO
            indice = '' if is_subsecao else parent_index if item.tipo != ItemTR.Tipo.NUMERICO else f'{parent_index}.{idx}'
            rows.append({
                'item': item,
                'indice': indice,
                'enum_prefix': enum_prefix(item, siblings),
                'is_subsecao': is_subsecao,
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


def termo_tabela_item_1_1(termo):
    for sessao in termo.sessoes.all():
        for row in build_item_rows(sessao):
            if row['indice'] == '1.1':
                return row['item']
    return None


def pesquisa_preco_itens(pesquisa):
    item = termo_tabela_item_1_1(pesquisa.termo)
    if not item:
        return TabelaItemLinha.objects.none()
    return item.tabela_linhas.order_by('ordem', 'id')


def pesquisa_preco_row_class(dias_sem_resposta):
    if dias_sem_resposta is None:
        return ''
    if dias_sem_resposta <= 3:
        return 'spi-pesquisa-row-verde'
    if dias_sem_resposta == 4:
        return 'spi-pesquisa-row-amarelo'
    if dias_sem_resposta == 5:
        return 'spi-pesquisa-row-laranja'
    if dias_sem_resposta == 6:
        return 'spi-pesquisa-row-vermelho'
    if dias_sem_resposta == 7:
        return 'spi-pesquisa-row-roxo'
    return 'spi-pesquisa-row-preto'


def pesquisa_fornecedor_tem_resposta(pesquisa_fornecedor):
    return bool(pesquisa_fornecedor.data_resposta and pesquisa_fornecedor.valores.exists())


def pesquisa_preco_context(pesquisa):
    hoje = timezone.localdate()
    itens = list(pesquisa_preco_itens(pesquisa))
    fornecedores = list(
        pesquisa.fornecedores_pesquisa
        .select_related('fornecedor')
        .prefetch_related('contatos', 'valores')
        .order_by('fornecedor__razao_social', 'id')
    )
    valores_por_fornecedor = {
        pf.id: {valor.item_id: valor for valor in pf.valores.all()}
        for pf in fornecedores
    }
    fornecedores_ctx = []

    for pf in fornecedores:
        valores = valores_por_fornecedor.get(pf.id, {})
        item_rows = []
        total = Decimal('0.00')
        for item in itens:
            valor = valores.get(item.id)
            preco_unitario = valor.preco_unitario if valor else None
            valor_total = (preco_unitario * item.quantidade).quantize(Decimal('0.01')) if preco_unitario is not None else None
            if valor_total is not None:
                total += valor_total
            item_rows.append({
                'item': item,
                'preco_unitario': preco_unitario,
                'valor_total': valor_total,
            })

        tem_resposta = bool(pf.data_resposta and valores)
        ultimo_contato = pf.contatos.all()[0].data_contato if pf.contatos.all() else None
        dias_sem_resposta = None
        if ultimo_contato and not tem_resposta:
            dias_sem_resposta = (hoje - ultimo_contato).days

        dias_validade = None
        validade_alerta = False
        vencimento = None
        if pf.data_resposta and pf.validade_orcamento_dias:
            vencimento = pf.data_resposta + timedelta(days=pf.validade_orcamento_dias)
            dias_validade = (vencimento - hoje).days
            validade_alerta = dias_validade <= 10

        total_contratacao = total
        if pesquisa.tipo == PesquisaPreco.Tipo.SERVICO and pesquisa.vigencia_meses:
            total_contratacao = (total * pesquisa.vigencia_meses).quantize(Decimal('0.01'))

        fornecedores_ctx.append({
            'pesquisa_fornecedor': pf,
            'fornecedor': pf.fornecedor,
            'itens': item_rows,
            'ultimo_contato': ultimo_contato,
            'dias_sem_resposta': dias_sem_resposta,
            'row_class': pesquisa_preco_row_class(dias_sem_resposta),
            'tem_resposta': tem_resposta,
            'total': total,
            'total_contratacao': total_contratacao,
            'vencimento': vencimento,
            'dias_validade': dias_validade,
            'validade_alerta': validade_alerta,
        })

    medias = []
    total_medio = Decimal('0.00')
    for item in itens:
        precos = [
            valores_por_fornecedor.get(pf.id, {}).get(item.id).preco_unitario
            for pf in fornecedores
            if valores_por_fornecedor.get(pf.id, {}).get(item.id)
        ]
        preco_medio = None
        total_item_medio = None
        if precos:
            preco_medio = (sum(precos) / Decimal(len(precos))).quantize(Decimal('0.01'))
            total_item_medio = (preco_medio * item.quantidade).quantize(Decimal('0.01'))
            total_medio += total_item_medio
        medias.append({
            'item': item,
            'preco_medio': preco_medio,
            'valor_total_medio': total_item_medio,
        })

    total_medio_contratacao = total_medio
    if pesquisa.tipo == PesquisaPreco.Tipo.SERVICO and pesquisa.vigencia_meses:
        total_medio_contratacao = (total_medio * pesquisa.vigencia_meses).quantize(Decimal('0.01'))

    return {
        'itens': itens,
        'fornecedores': fornecedores_ctx,
        'medias': medias,
        'total_medio': total_medio,
        'total_medio_contratacao': total_medio_contratacao,
    }


def build_etp_item_rows(sessao):
    itens = list(sessao.itens.select_related('parent').order_by('parent_id', 'ordem', 'id'))
    by_parent = defaultdict(list)
    for item in itens:
        by_parent[item.parent_id].append(item)
    rows = []

    def walk(parent_id, parent_index, depth):
        siblings = by_parent.get(parent_id, [])
        for item in siblings:
            idx = etp_sibling_index(item, siblings)
            is_subsecao = item.tipo == ItemEtpTic.Tipo.SUBSECAO
            indice = '' if is_subsecao else parent_index if item.tipo != ItemEtpTic.Tipo.NUMERICO else f'{parent_index}.{idx}'
            rows.append({
                'item': item,
                'indice': indice,
                'enum_prefix': etp_enum_prefix(item, siblings),
                'is_subsecao': is_subsecao,
                'depth': depth,
                'indent': depth * 1.5,
            })
            child_parent_index = indice if item.tipo == ItemEtpTic.Tipo.NUMERICO else parent_index
            walk(item.id, child_parent_index, depth + 1)

    walk(None, str(sessao.ordem), 0)
    return rows


def build_etp_tree(etp):
    return [{'sessao': sessao, 'rows': build_etp_item_rows(sessao)} for sessao in etp.sessoes.all()]


def item_descendant_ids(item):
    ids = set()
    stack = list(item.filhos.all())
    while stack:
        child = stack.pop()
        ids.add(child.id)
        stack.extend(list(child.filhos.all()))
    return ids


def etp_item_descendant_ids(item):
    ids = set()
    stack = list(item.filhos.all())
    while stack:
        child = stack.pop()
        ids.add(child.id)
        stack.extend(list(child.filhos.all()))
    return ids


def clear_item_children(item):
    child_count = len(item_descendant_ids(item))
    item.filhos.all().delete()
    return child_count


def clear_etp_item_children(item):
    child_count = len(etp_item_descendant_ids(item))
    item.filhos.all().delete()
    return child_count


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


def move_etp_item(item, target, action, target_sessao=None, child_position=None):
    if action not in {'after', 'child'}:
        raise ValueError('Acao de movimentacao invalida.')
    if target and target.id == item.id:
        raise ValueError('Nao e possivel mover um item para ele mesmo.')
    if target and target.id in etp_item_descendant_ids(item):
        raise ValueError('Nao e possivel mover um item para dentro de um descendente.')

    old_sessao = item.sessao
    old_parent_id = item.parent_id

    with transaction.atomic():
        item = ItemEtpTic.objects.select_for_update().get(pk=item.pk)
        if action == 'child' and target:
            new_sessao = target.sessao
            new_parent = target
            siblings = list(new_sessao.itens.filter(parent=new_parent).exclude(pk=item.pk).order_by('ordem', 'id'))
            ordered = _insert_at_position(siblings, item, child_position)
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
        else:
            new_sessao = target_sessao
            new_parent = None
            siblings = list(new_sessao.itens.filter(parent=None).exclude(pk=item.pk).order_by('ordem', 'id'))
            ordered = _insert_at_position(siblings, item, child_position)

        item.sessao = new_sessao
        item.parent = new_parent
        item.ordem = 1
        item.save(update_fields=['sessao', 'parent', 'ordem', 'atualizado_em'])
        _cascade_etp_sessao(item, new_sessao)

        normalize_etp_items(old_sessao, old_parent_id)
        normalize_etp_items(new_sessao, new_parent.id if new_parent else None)
        if action == 'after' and target or action == 'child':
            for idx, sibling in enumerate(ordered, start=1):
                ItemEtpTic.objects.filter(pk=sibling.pk).update(ordem=idx)


def duplicate_etp_item(item, target, action, target_sessao=None, child_position=None):
    if action not in {'after', 'child'}:
        raise ValueError('Acao de duplicacao invalida.')
    if target and target.id == item.id:
        raise ValueError('Nao e possivel duplicar um item para ele mesmo.')
    if target and target.id in etp_item_descendant_ids(item):
        raise ValueError('Nao e possivel duplicar um item para dentro de um descendente.')

    with transaction.atomic():
        item = ItemEtpTic.objects.select_related('sessao', 'parent').get(pk=item.pk)
        if action == 'child' and target:
            new_sessao = target.sessao
            new_parent = target
            ordered = list(new_sessao.itens.filter(parent=new_parent).order_by('ordem', 'id'))
        elif target:
            new_sessao = target.sessao
            new_parent = target.parent
            ordered = list(new_sessao.itens.filter(parent=new_parent).order_by('ordem', 'id'))
        else:
            new_sessao = target_sessao
            new_parent = None
            ordered = list(new_sessao.itens.filter(parent=None).order_by('ordem', 'id'))

        duplicate = _copy_etp_item_tree(item, new_sessao, new_parent, 1)

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
                ItemEtpTic.objects.filter(pk=sibling.pk).update(ordem=idx)
        elif action == 'child':
            reordered = _insert_at_position(ordered, duplicate, child_position)
            for idx, sibling in enumerate(reordered, start=1):
                ItemEtpTic.objects.filter(pk=sibling.pk).update(ordem=idx)
        else:
            normalize_etp_items(new_sessao, new_parent.id if new_parent else None)

        return duplicate


def duplicate_termo(termo):
    with transaction.atomic():
        termo = TermoReferencia.objects.get(pk=termo.pk)
        duplicate = TermoReferencia.objects.create(
            nome=f'Copia de {termo.nome}',
            numero_processo=termo.numero_processo,
            link=termo.link,
        )
        for sessao in termo.sessoes.order_by('ordem', 'id'):
            new_sessao = SessaoTR.objects.create(
                termo=duplicate,
                titulo=sessao.titulo,
                ordem=sessao.ordem,
            )
            for item in sessao.itens.filter(parent=None).order_by('ordem', 'id'):
                _copy_item_tree(item, new_sessao, None, item.ordem)
        return duplicate


def duplicate_etp(etp):
    with transaction.atomic():
        etp = EtpTic.objects.get(pk=etp.pk)
        duplicate = EtpTic.objects.create(
            nome=f'Copia de {etp.nome}',
            numero_processo=etp.numero_processo,
            link=etp.link,
            status=etp.status,
            secao_atual=etp.secao_atual,
            usa_editor_dinamico=etp.usa_editor_dinamico,
            descricao_necessidade=etp.descricao_necessidade,
            area_requisitante=etp.area_requisitante,
            responsavel_area=etp.responsavel_area,
            necessidades_negocio=etp.necessidades_negocio,
            necessidades_tecnologicas=etp.necessidades_tecnologicas,
            demais_requisitos=etp.demais_requisitos,
            estimativa_demanda=etp.estimativa_demanda,
            levantamento_solucoes=etp.levantamento_solucoes,
            analise_comparativa_solucoes=etp.analise_comparativa_solucoes,
            solucoes_inviaveis=etp.solucoes_inviaveis,
            analise_comparativa_custos_tco=etp.analise_comparativa_custos_tco,
            descricao_solucao_tic=etp.descricao_solucao_tic,
            estimativa_custo_valor=etp.estimativa_custo_valor,
            estimativa_custo_texto=etp.estimativa_custo_texto,
            justificativa_tecnica=etp.justificativa_tecnica,
            justificativa_economica=etp.justificativa_economica,
            beneficios_contratacao=etp.beneficios_contratacao,
            providencias_adotadas=etp.providencias_adotadas,
            declaracao_viabilidade=etp.declaracao_viabilidade,
            justificativa_viabilidade=etp.justificativa_viabilidade,
        )
        for sessao in etp.sessoes.order_by('ordem', 'id'):
            new_sessao = SessaoEtpTic.objects.create(
                etp=duplicate,
                titulo=sessao.titulo,
                ordem=sessao.ordem,
            )
            for item in sessao.itens.filter(parent=None).order_by('ordem', 'id'):
                _copy_etp_item_tree(item, new_sessao, None, item.ordem)
        return duplicate


def duplicate_dfd(dfd):
    with transaction.atomic():
        dfd = Dfd.objects.get(pk=dfd.pk)
        duplicate = Dfd.objects.create(
            nome=f'Copia de {dfd.nome}',
            numero_processo=dfd.numero_processo,
            status=dfd.status,
            secao_atual=dfd.secao_atual,
            informacoes_preliminares=dfd.informacoes_preliminares,
            descricao_objeto=dfd.descricao_objeto,
            objeto_nao_luxo=dfd.objeto_nao_luxo,
            justificativa_necessidade=dfd.justificativa_necessidade,
            estimativa_quantidade_valores=dfd.estimativa_quantidade_valores,
            vinculacao_outro_dfd=dfd.vinculacao_outro_dfd,
            responsaveis=dfd.responsaveis,
        )
        for item in dfd.itens_tabela.order_by('ordem', 'id'):
            DfdItemTabela.objects.create(
                dfd=duplicate,
                ordem=item.ordem,
                especificacao=item.especificacao,
                catmat=item.catmat,
                siafisico=item.siafisico,
                unidade_medida=item.unidade_medida,
                quantidade=item.quantidade,
                valor_unitario=item.valor_unitario,
                valor_total=item.valor_total,
            )
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


def _copy_etp_item_tree(item, sessao, parent, ordem):
    duplicate = ItemEtpTic.objects.create(
        sessao=sessao,
        parent=parent,
        tipo=item.tipo,
        texto=item.texto,
        ordem=ordem,
    )
    for idx, child in enumerate(item.filhos.order_by('ordem', 'id'), start=1):
        _copy_etp_item_tree(child, sessao, duplicate, idx)
    return duplicate


def _cascade_sessao(item, sessao):
    for child in item.filhos.all():
        if child.sessao_id != sessao.id:
            child.sessao = sessao
            child.save(update_fields=['sessao'])
        _cascade_sessao(child, sessao)


def _cascade_etp_sessao(item, sessao):
    for child in item.filhos.all():
        if child.sessao_id != sessao.id:
            child.sessao = sessao
            child.save(update_fields=['sessao'])
        _cascade_etp_sessao(child, sessao)
