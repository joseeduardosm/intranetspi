from django.contrib import admin

from .models import (
    Dfd,
    DfdItemTabela,
    EtpTic,
    Fornecedor,
    ItemEtpTic,
    ItemTR,
    PesquisaPreco,
    PesquisaPrecoContato,
    PesquisaPrecoFornecedor,
    PesquisaPrecoItemValor,
    SessaoEtpTic,
    SessaoTR,
    TabelaItemLinha,
    TermoReferencia,
)


@admin.register(EtpTic)
class EtpTicAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'numero_processo', 'status', 'usa_editor_dinamico', 'secao_atual', 'atualizado_em', 'atualizado_por')
    search_fields = ('nome', 'numero_processo')


@admin.register(TermoReferencia)
class TermoReferenciaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'numero_processo', 'atualizado_em', 'atualizado_por')
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


@admin.register(SessaoEtpTic)
class SessaoEtpTicAdmin(admin.ModelAdmin):
    list_display = ('etp', 'ordem', 'titulo')
    list_filter = ('etp',)


@admin.register(ItemEtpTic)
class ItemEtpTicAdmin(admin.ModelAdmin):
    list_display = ('sessao', 'parent', 'ordem', 'texto')
    list_filter = ('sessao__etp',)


@admin.register(TabelaItemLinha)
class TabelaItemLinhaAdmin(admin.ModelAdmin):
    list_display = ('item', 'ordem', 'descricao', 'quantidade')
    list_filter = ('item__sessao__termo',)


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ('razao_social', 'cnpj', 'telefone', 'contato', 'email_contato')
    search_fields = ('razao_social', 'cnpj', 'contato', 'email_contato')


@admin.register(PesquisaPreco)
class PesquisaPrecoAdmin(admin.ModelAdmin):
    list_display = ('termo', 'tipo', 'pesquisador_nome', 'pesquisador_email', 'pesquisador_cargo', 'vigencia_meses', 'atualizado_em')
    list_filter = ('tipo',)
    search_fields = ('termo__nome', 'termo__numero_processo', 'pesquisador_nome', 'pesquisador_email')


@admin.register(PesquisaPrecoFornecedor)
class PesquisaPrecoFornecedorAdmin(admin.ModelAdmin):
    list_display = ('pesquisa', 'fornecedor', 'data_resposta', 'validade_orcamento_dias', 'documento_fornecedor')
    list_filter = ('pesquisa__tipo', 'fornecedor')


@admin.register(PesquisaPrecoContato)
class PesquisaPrecoContatoAdmin(admin.ModelAdmin):
    list_display = ('pesquisa_fornecedor', 'data_contato', 'criado_em')
    list_filter = ('data_contato',)


@admin.register(PesquisaPrecoItemValor)
class PesquisaPrecoItemValorAdmin(admin.ModelAdmin):
    list_display = ('pesquisa_fornecedor', 'item', 'preco_unitario')
    list_filter = ('pesquisa_fornecedor__pesquisa',)

# Register your models here.
