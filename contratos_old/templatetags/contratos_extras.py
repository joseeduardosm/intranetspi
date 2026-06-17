# Criado por José Eduardo Santana Martins e OpenAI Codex em 07/06/2026
# Objetivo: Centralizar formatações de apresentação específicas do módulo de contratos.

from decimal import Decimal, InvalidOperation

from django import template


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
