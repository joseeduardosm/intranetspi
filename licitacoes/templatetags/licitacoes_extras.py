# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Disponibilizar filtros de template para marcações, campos dinâmicos e e-mails.

from django import template
from django.utils.safestring import mark_safe

from licitacoes.services import red_marked_html


register = template.Library()


@register.filter
def red_marks(value):
    """Renderiza marcações em vermelho geradas pelo serviço de texto."""

    return mark_safe(red_marked_html(value))


@register.filter
def get_item_field(form, item):
    """Recupera o campo de preço unitário criado dinamicamente para um item."""

    return form[f'preco_item_{item.id}']


@register.filter
def split_emails(value):
    """Divide a lista textual de e-mails usada em fornecedores."""

    return [email.strip() for email in (value or '').split(';') if email.strip()]
