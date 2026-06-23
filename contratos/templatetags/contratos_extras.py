# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Centralizar filtros de formatação (brl) e tags do módulo de contratos.

from decimal import Decimal, InvalidOperation
from django import template
from django.utils import timezone

register = template.Library()

AUDITORIA_EXTRA_LABELS = {
    'secoes_alteradas': 'Seções alteradas',
    'medicoes_alteradas': 'Medições alteradas',
    'itens_alterados': 'Itens alterados',
}

SECOES_AUDITORIA_LABELS = {
    'aceite_provisorio': 'Aceite provisório',
    'medicao': 'Medição',
    'aceite_definitivo': 'Aceite definitivo',
    'nota_principal': 'Nota fiscal principal',
    'nota_adicional': 'Nota fiscal adicional',
    'observacoes_finais': 'Observações finais',
}


def _quantize_decimal(value):
    """Padroniza casas decimais para exibição consistente nas tabelas do módulo."""

    return Decimal(value).quantize(Decimal('0.01'))


@register.filter
def brl(value):
    """Formata valores monetários no padrão brasileiro com milhar e duas casas."""

    try:
        number = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        return '0,00'
    formatted = f'{number:,.2f}'
    return formatted.replace(',', '_').replace('.', ',').replace('_', '.')


@register.simple_tag
def item_field(form, pk, prefix):
    return form[f'{prefix}_{pk}']


@register.simple_tag
def item_field_errors(form, pk, prefix):
    return form[f'{prefix}_{pk}'].errors


@register.simple_tag
def item_field_id(form, pk, prefix):
    return form[f'{prefix}_{pk}'].id_for_label


@register.simple_tag
def item_audit_footer(item, prefix):
    """Mostra o rodapé com usuário e data/hora do último preenchimento do campo."""

    usuario = getattr(item, f'{prefix}_preenchida_por', None)
    data = getattr(item, f'{prefix}_preenchida_em', None)
    if usuario is None and data is None:
        return ''

    nome = ''
    if usuario is not None:
        perfil = getattr(usuario, 'perfil', None)
        nome = getattr(perfil, 'nome_completo', None) or usuario.get_full_name() or usuario.username

    partes = []
    if nome:
        partes.append(f'Preenchido por {nome}')
    if data is not None:
        partes.append(timezone.localtime(data).strftime('%d/%m/%Y %H:%M'))
    return ' • '.join(partes)


@register.filter
def subtotal_ponderado(resposta):
    """Calcula o subtotal ponderado do item usando a nota vigente persistida."""

    nota = getattr(resposta, 'nota_valor', None)
    if nota is None:
        nota = getattr(resposta, 'nota_vigente', None)
    peso = getattr(resposta, 'item_peso_percentual', Decimal('0.00')) or Decimal('0.00')
    return _quantize_decimal((Decimal(nota or 0) * Decimal(peso)) / Decimal('100.00'))


@register.simple_tag
def grupo_total_ponderado(respostas):
    """Soma os subtotais ponderados do grupo para exibir o total consolidado."""

    total = Decimal('0.00')
    for resposta in respostas:
        total += subtotal_ponderado(resposta)
    return _quantize_decimal(total)


def _rotulo_auditoria_extra(chave):
    """Traduz as chaves internas da auditoria para títulos amigáveis na interface."""

    return AUDITORIA_EXTRA_LABELS.get(chave, str(chave).replace('_', ' ').capitalize())


def _rotulo_secao_auditoria(valor):
    """Traduz os identificadores técnicos das seções operacionais exibidas no histórico."""

    return SECOES_AUDITORIA_LABELS.get(valor, str(valor).replace('_', ' ').capitalize())


def _serializar_registro_auditoria(registro):
    """Resume dicionários operacionais em uma frase legível na trilha de auditoria."""

    if not isinstance(registro, dict):
        return str(registro)

    if {'item', 'antes', 'depois'}.issubset(registro.keys()):
        return f"{registro['item']}: {registro['antes']} -> {registro['depois']}"

    partes = []
    for chave, valor in registro.items():
        partes.append(f"{_rotulo_auditoria_extra(chave)}: {valor}")
    return ' • '.join(partes)


@register.inclusion_tag('contratos/partials/auditoria_extra.html')
def render_auditoria_extra(extra):
    """Renderiza os metadados extras da auditoria sem expor listas Python cruas na interface."""

    entradas = []
    for chave, valor in (extra or {}).items():
        entrada = {
            'titulo': _rotulo_auditoria_extra(chave),
            'tipo': 'texto',
            'valor': valor,
        }

        if chave == 'secoes_alteradas' and isinstance(valor, list):
            entrada['tipo'] = 'lista'
            entrada['itens'] = [_rotulo_secao_auditoria(item) for item in valor]
        elif isinstance(valor, list):
            entrada['tipo'] = 'lista'
            entrada['itens'] = [_serializar_registro_auditoria(item) for item in valor]
        elif isinstance(valor, dict):
            entrada['tipo'] = 'lista'
            entrada['itens'] = [
                f'{_rotulo_auditoria_extra(item_chave)}: {item_valor}'
                for item_chave, item_valor in valor.items()
            ]

        entradas.append(entrada)

    return {'entradas_auditoria_extra': entradas}
