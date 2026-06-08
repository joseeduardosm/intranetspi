# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Disponibilizar acessos dinâmicos a campos de formulários do Contratos V2 nas telas operacionais.

from django import template


register = template.Library()


@register.simple_tag
def item_field(form, pk, prefix):
    return form[f'{prefix}_{pk}']


@register.simple_tag
def item_field_errors(form, pk, prefix):
    return form[f'{prefix}_{pk}'].errors


@register.simple_tag
def item_field_id(form, pk, prefix):
    return form[f'{prefix}_{pk}'].id_for_label
