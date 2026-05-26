from django import template
from django.utils.safestring import mark_safe

from licitacoes.services import red_marked_html


register = template.Library()


@register.filter
def red_marks(value):
    return mark_safe(red_marked_html(value))


@register.filter
def get_item_field(form, item):
    return form[f'preco_item_{item.id}']


@register.filter
def split_emails(value):
    return [email.strip() for email in (value or '').split(';') if email.strip()]
