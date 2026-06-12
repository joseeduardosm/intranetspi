# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Disponibilizar acessos dinâmicos a campos de formulários do Contratos V2 nas telas operacionais.

from django import template
from django.utils import timezone


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
