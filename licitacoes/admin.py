from django.contrib import admin

from .models import Dfd, DfdItemTabela, EtpTic, ItemTR, SessaoTR, TabelaItemLinha, TermoReferencia


@admin.register(EtpTic)
class EtpTicAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'numero_processo', 'status', 'secao_atual', 'atualizado_em')
    search_fields = ('nome', 'numero_processo')


@admin.register(TermoReferencia)
class TermoReferenciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'numero_processo', 'atualizado_em')
    search_fields = ('nome', 'numero_processo')


@admin.register(Dfd)
class DfdAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'numero_processo', 'status', 'secao_atual', 'atualizado_em')
    search_fields = ('nome', 'numero_processo')


@admin.register(DfdItemTabela)
class DfdItemTabelaAdmin(admin.ModelAdmin):
    list_display = ('dfd', 'ordem', 'especificacao', 'quantidade', 'valor_total')
    list_filter = ('dfd',)


@admin.register(SessaoTR)
class SessaoTRAdmin(admin.ModelAdmin):
    list_display = ('termo', 'ordem', 'titulo')
    list_filter = ('termo',)


@admin.register(ItemTR)
class ItemTRAdmin(admin.ModelAdmin):
    list_display = ('sessao', 'parent', 'tipo', 'ordem', 'texto')
    list_filter = ('tipo', 'sessao')


@admin.register(TabelaItemLinha)
class TabelaItemLinhaAdmin(admin.ModelAdmin):
    list_display = ('item', 'ordem', 'descricao', 'quantidade')
    list_filter = ('item__sessao__termo',)

# Register your models here.
