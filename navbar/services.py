from collections import defaultdict

from .models import NavbarItem


def active_navbar_tree():
    items = list(NavbarItem.objects.filter(ativo=True).select_related('parent').order_by('ordem', 'titulo', 'id'))
    children_by_parent = defaultdict(list)
    roots = []
    for item in items:
        if item.parent_id:
            children_by_parent[item.parent_id].append(item)
        else:
            roots.append(item)
    return [{'item': item, 'children': children_by_parent.get(item.id, [])} for item in roots]
