# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Centralizar filtros de formatação (brl) e tags do módulo de contratos.

from decimal import Decimal, InvalidOperation
from django import template
from django.utils import timezone

register = template.Library()


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
