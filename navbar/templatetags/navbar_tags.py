from django import template
from acls.models import Recurso
from acls.utils import obter_nivel_acesso
from navbar.services import active_navbar_tree

register = template.Library()


@register.simple_tag
def navbar_items():
    return active_navbar_tree()


@register.simple_tag
def user_modules(user):
    if not user or user.is_anonymous:
        return []
    recursos = Recurso.objects.all().order_by('nome')
    acessos = []
    for r in recursos:
        if obter_nivel_acesso(user, r.slug) is not None:
            url = f"/{r.slug.replace('_', '-')}/"
            acessos.append({
                'nome': r.nome,
                'url': url,
                'slug': r.slug
            })
    return acessos

