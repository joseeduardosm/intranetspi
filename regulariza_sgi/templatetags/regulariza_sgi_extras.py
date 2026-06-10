# Criado por Codex em 09/06/2026
# Objetivo: Disponibilizar filtros auxiliares de formatação para o Regulariza SGI.

from decimal import Decimal

from django import template


register = template.Library()


@register.filter
def br_money(value):
    """Formata Decimal no padrão monetário brasileiro sem símbolo."""

    if value in (None, ''):
        return '-'
    inteiro, fracionario = f'{Decimal(value):.2f}'.split('.')
    inteiro_formatado = f'{int(inteiro):,}'.replace(',', '.')
    return f'{inteiro_formatado},{fracionario}'
