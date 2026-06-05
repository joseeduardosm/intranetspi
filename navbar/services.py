# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Montar a árvore ativa da navbar e controlar normalização/reordenação de itens.

from collections import defaultdict

from django.db import transaction

from .models import NavbarItem


def active_navbar_tree():
    """Retorna itens ativos em estrutura de menu principal com filhos ativos."""

    items = list(NavbarItem.objects.filter(ativo=True).select_related('parent').order_by('ordem', 'titulo', 'id'))
    children_by_parent = defaultdict(list)
    roots = []
    for item in items:
        if item.parent_id:
            children_by_parent[item.parent_id].append(item)
        else:
            roots.append(item)
    return [{'item': item, 'children': children_by_parent.get(item.id, [])} for item in roots]


def ordered_siblings(parent_id):
    """Lista itens irmãos de um mesmo pai na ordem de exibição."""

    return list(
        NavbarItem.objects.filter(parent_id=parent_id)
        .select_related('parent')
        .order_by('ordem', 'titulo', 'id')
    )


@transaction.atomic
def normalize_navbar_branch(parent_id):
    """Renumera a ordem dos irmãos de uma ramificação da navbar."""

    siblings = ordered_siblings(parent_id)
    for index, item in enumerate(siblings, start=1):
        if item.ordem != index:
            NavbarItem.objects.filter(pk=item.pk).update(ordem=index)


@transaction.atomic
def move_navbar_item(item, direction):
    """Move um item para cima ou para baixo entre irmãos do mesmo nível."""

    siblings = ordered_siblings(item.parent_id)
    index_by_id = {sibling.id: index for index, sibling in enumerate(siblings)}
    current_index = index_by_id.get(item.id)
    if current_index is None:
        return False

    target_index = current_index - 1 if direction == 'up' else current_index + 1
    if target_index < 0 or target_index >= len(siblings):
        return False

    siblings[current_index], siblings[target_index] = siblings[target_index], siblings[current_index]
    for index, sibling in enumerate(siblings, start=1):
        if sibling.ordem != index:
            NavbarItem.objects.filter(pk=sibling.pk).update(ordem=index)
    return True


def navbar_move_state(items):
    """Calcula quais itens da listagem podem subir ou descer."""

    state = {}
    siblings_by_parent = {}

    for item in items:
        siblings_by_parent.setdefault(item.parent_id, ordered_siblings(item.parent_id))

    for parent_id, siblings in siblings_by_parent.items():
        total = len(siblings)
        for index, sibling in enumerate(siblings):
            state[sibling.id] = {
                'up': index > 0,
                'down': index < total - 1,
            }

    return state
