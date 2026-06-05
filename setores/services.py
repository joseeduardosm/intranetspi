from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Prefetch

from .models import SetorNode, UserSetorMembership


User = get_user_model()


def visible_users_queryset():
    return User.objects.filter(is_active=True).order_by('first_name', 'username')


def user_display_name(user):
    return (user.get_full_name() or user.first_name or user.username).strip()


def user_profile_payload(user):
    try:
        perfil = user.perfil
    except ObjectDoesNotExist:
        perfil = None

    return {
        'nome': user_display_name(user),
        'cargo': perfil.cargo if perfil else '',
        'setor': perfil.setor if perfil else '',
        'email': user.email or '',
        'ramal': perfil.ramal if perfil else '',
        'celular': perfil.celular if perfil else '',
        'whatsapp_url': perfil.whatsapp_url if perfil else '',
        'local': perfil.andar_bloco_display if perfil else '',
        'photo_url': perfil.foto.url if perfil and perfil.foto else '',
    }



def setor_choice_pairs(include_inactive=False):
    queryset = SetorNode.objects.select_related('group')
    if not include_inactive:
        queryset = queryset.filter(ativo=True)
    return [(setor.pk, setor.group.name) for setor in queryset.order_by('group__name', 'id')]


def primary_setor_for_user(user):
    if not user or not user.is_authenticated:
        return None
    perfil = getattr(user, 'perfil', None)
    memberships = list(
        user.setor_memberships.select_related('setor__group').order_by('setor__group__name', 'setor_id')
    )
    if perfil and perfil.setor:
        for membership in memberships:
            if membership.setor.group.name == perfil.setor:
                return membership.setor
    return memberships[0].setor if memberships else None


@transaction.atomic
def sync_user_memberships_for_setor(setor, selected_users):
    selected_ids = {user.id for user in selected_users}
    current_memberships = UserSetorMembership.objects.filter(setor=setor).select_related('user')
    current_ids = {membership.user_id for membership in current_memberships}

    for user in selected_users:
        membership, _created = UserSetorMembership.objects.get_or_create(user=user, setor=setor)
        membership.user.groups.add(setor.group)

    stale_memberships = current_memberships.exclude(user_id__in=selected_ids)
    for membership in stale_memberships:
        membership.user.groups.remove(setor.group)
        perfil = getattr(membership.user, 'perfil', None)
        if perfil and perfil.setor == setor.group.name:
            perfil.setor = ''
            perfil.save(update_fields=['setor', 'atualizado_em'])
        membership.delete()


@transaction.atomic
def ensure_user_primary_setor(user, setor):
    if not user or not setor:
        return
    UserSetorMembership.objects.get_or_create(user=user, setor=setor)
    user.groups.add(setor.group)
    perfil = getattr(user, 'perfil', None)
    if perfil and perfil.setor != setor.group.name:
        perfil.setor = setor.group.name
        perfil.save(update_fields=['setor', 'atualizado_em'])


def build_setor_tree():
    memberships_qs = UserSetorMembership.objects.select_related('user', 'user__perfil').order_by(
        'user__first_name', 'user__username', 'id'
    )
    setores = list(
        SetorNode.objects.filter(ativo=True)
        .exclude(group__name__iexact='administradores')
        .select_related('group', 'parent__group', 'lider', 'lider__perfil')
        .prefetch_related(Prefetch('memberships', queryset=memberships_qs))
        .order_by('group__name', 'id')
    )
    
    setor_ids = {s.id for s in setores}
    by_parent = {}
    for setor in setores:
        by_parent.setdefault(setor.parent_id, []).append(setor)

    def build_node(setor, level=0, visited_ids=None):
        if visited_ids is None:
            visited_ids = set()
        
        if setor.id in visited_ids:
            return None
            
        visited_ids.add(setor.id)
        users = [membership.user for membership in setor.memberships.all()]
        
        children_nodes = []
        for child in by_parent.get(setor.id, []):
            child_node = build_node(child, level + 1, visited_ids.copy())
            if child_node:
                children_nodes.append(child_node)
                
        return {
            'setor': setor,
            'level': level,
            'lider_nome': user_display_name(setor.lider) if setor.lider_id else '',
            'lider_payload': user_profile_payload(setor.lider) if setor.lider_id else None,
            'usuarios': [
                {
                    'user': user,
                    'label': user_display_name(user),
                    'payload': user_profile_payload(user),
                }
                for user in users
            ],
            'children': children_nodes,
        }

    roots = [s for s in setores if s.parent_id is None or s.parent_id not in setor_ids]
    
    tree = []
    for r in roots:
        node = build_node(r, 0)
        if node:
            tree.append(node)
            
    return tree


def group_name_exists(name, exclude_group_id=None):
    queryset = Group.objects.filter(name__iexact=name.strip())
    if exclude_group_id:
        queryset = queryset.exclude(pk=exclude_group_id)
    return queryset.exists()
