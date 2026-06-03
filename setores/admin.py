from django.contrib import admin

from .models import SetorNode, UserSetorMembership


@admin.register(SetorNode)
class SetorNodeAdmin(admin.ModelAdmin):
    list_display = ('id', 'group', 'parent', 'lider', 'ativo')
    search_fields = ('group__name', 'parent__group__name', 'lider__username', 'lider__first_name')
    autocomplete_fields = ('parent', 'lider')


@admin.register(UserSetorMembership)
class UserSetorMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'setor', 'criado_em')
    search_fields = ('user__username', 'user__first_name', 'setor__group__name')
    autocomplete_fields = ('user', 'setor')

# Register your models here.
