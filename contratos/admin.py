# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Expor o cadastro inicial do Contratos V2 no admin do Django.

from django.contrib import admin

from .models import (
    AvaliacaoQualidadeCompetencia,
    ChecklistCompetenciaItem,
    ChecklistModeloItem,
    ChecklistModelo,
    CompetenciaPagamento,
    ContratoItem,
    Contrato,
    EscalaNotaAvaliacao,
    EscalaNotaAvaliacaoPadraoGlobal,
    FaixaLiberacaoAvaliacao,
    FaixaLiberacaoAvaliacaoPadraoGlobal,
    FormularioAvaliacao,
    FormularioAvaliacaoPadraoGlobal,
    GrupoAvaliacao,
    GrupoAvaliacaoPadraoGlobal,
    ItemAvaliacao,
    ItemAvaliacaoPadraoGlobal,
    MedicaoItemCompetencia,
)


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = (
        'numero_contrato',
        'apelido',
        'empresa_contratada',
        'data_inicio_vigencia',
        'situacao_forcada',
    )
    search_fields = (
        'numero_contrato',
        'apelido',
        'objeto',
        'empresa_contratada__razao_social',
    )


@admin.register(ContratoItem)
class ContratoItemAdmin(admin.ModelAdmin):
    list_display = (
        'contrato',
        'ordem',
        'descricao',
        'codigo_siafisico',
        'codigo_catmat_catser',
        'quantidade',
        'valor_unitario',
        'valor_subtotal',
    )
    search_fields = ('contrato__numero_contrato', 'contrato__apelido', 'descricao', 'codigo_siafisico', 'codigo_catmat_catser')


admin.site.register(ChecklistModelo)
admin.site.register(ChecklistModeloItem)
admin.site.register(FormularioAvaliacao)
admin.site.register(FormularioAvaliacaoPadraoGlobal)
admin.site.register(EscalaNotaAvaliacao)
admin.site.register(EscalaNotaAvaliacaoPadraoGlobal)
admin.site.register(FaixaLiberacaoAvaliacao)
admin.site.register(FaixaLiberacaoAvaliacaoPadraoGlobal)
admin.site.register(GrupoAvaliacao)
admin.site.register(GrupoAvaliacaoPadraoGlobal)
admin.site.register(ItemAvaliacao)
admin.site.register(ItemAvaliacaoPadraoGlobal)
admin.site.register(CompetenciaPagamento)
admin.site.register(ChecklistCompetenciaItem)
admin.site.register(MedicaoItemCompetencia)
admin.site.register(AvaliacaoQualidadeCompetencia)

from .models import EmpresaContratada
admin.site.register(EmpresaContratada)
