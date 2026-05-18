from django.contrib import admin

from .models import EtpTic, ItemTR, SessaoTR, TermoReferencia


@admin.register(EtpTic)
class EtpTicAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'numero_processo', 'status', 'secao_atual', 'atualizado_em')
    search_fields = ('nome', 'numero_processo')


@admin.register(TermoReferencia)
class TermoReferenciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'numero_processo', 'atualizado_em')
    search_fields = ('nome', 'numero_processo')


@admin.register(SessaoTR)
class SessaoTRAdmin(admin.ModelAdmin):
    list_display = ('termo', 'ordem', 'titulo')
    list_filter = ('termo',)


@admin.register(ItemTR)
class ItemTRAdmin(admin.ModelAdmin):
    list_display = ('sessao', 'parent', 'tipo', 'ordem', 'texto')
    list_filter = ('tipo', 'sessao')

# Register your models here.
