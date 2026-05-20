from django import template
from django.utils.safestring import mark_safe

from licitacoes.services import red_marked_html


register = template.Library()


@register.filter
def red_marks(value):
    return mark_safe(red_marked_html(value))
