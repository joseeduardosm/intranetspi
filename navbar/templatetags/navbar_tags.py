from django import template

from navbar.services import active_navbar_tree

register = template.Library()


@register.simple_tag
def navbar_items():
    return active_navbar_tree()
