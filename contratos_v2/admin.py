# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Expor o cadastro inicial do Contratos V2 no admin do Django.

from django.contrib import admin

from .models import (
    AvaliacaoQualidadeCompetenciaV2,
    ChecklistCompetenciaItemV2,
    ChecklistModeloItemV2,
    ChecklistModeloV2,
    CompetenciaPagamentoV2,
    ContratoItemV2,
    ContratoV2,
    EscalaNotaAvaliacaoV2,
    FaixaLiberacaoAvaliacaoV2,
    FormularioAvaliacaoV2,
    GrupoAvaliacaoV2,
    ItemAvaliacaoV2,
    MedicaoItemCompetenciaV2,
)


@admin.register(ContratoV2)
class ContratoV2Admin(admin.ModelAdmin):
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


@admin.register(ContratoItemV2)
class ContratoItemV2Admin(admin.ModelAdmin):
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


admin.site.register(ChecklistModeloV2)
admin.site.register(ChecklistModeloItemV2)
admin.site.register(FormularioAvaliacaoV2)
admin.site.register(EscalaNotaAvaliacaoV2)
admin.site.register(FaixaLiberacaoAvaliacaoV2)
admin.site.register(GrupoAvaliacaoV2)
admin.site.register(ItemAvaliacaoV2)
admin.site.register(CompetenciaPagamentoV2)
admin.site.register(ChecklistCompetenciaItemV2)
admin.site.register(MedicaoItemCompetenciaV2)
admin.site.register(AvaliacaoQualidadeCompetenciaV2)
