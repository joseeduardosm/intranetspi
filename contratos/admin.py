# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Registrar o domínio de contratos no Django Admin para suporte operacional.

from django.contrib import admin

from .models import (
    AvaliacaoCriterioCompetencia,
    AvaliacaoQualidadeCompetencia,
    ChecklistPagamentoAnexo,
    ChecklistPagamentoItem,
    ChecklistPagamentoModelo,
    CompetenciaPagamento,
    Contrato,
    ContratoDetalhamentoItem,
    ContratoItem,
    CriterioAvaliacaoQualidade,
    DocumentoContrato,
    EmpresaContratada,
    EventoFinanceiroContrato,
    EventoFinanceiroItem,
    GrupoAvaliacaoQualidade,
    MemoriaRetroatividade,
    MedicaoItemCompetencia,
    ModeloAvaliacaoQualidade,
    OcorrenciaContrato,
    OcorrenciaContratoAnexo,
    ResponsavelEmpresa,
    TermoAditivo,
)


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    """Admin resumido do contrato com campos de busca e filtros principais."""

    list_display = ('numero_contrato', 'apelido', 'empresa_contratada', 'data_inicio_vigencia', 'valor_global')
    search_fields = ('numero_contrato', 'apelido', 'objeto', 'empresa_contratada__razao_social')
    list_filter = ('empresa_contratada', 'situacao_forcada')


for model in [
    EmpresaContratada,
    ResponsavelEmpresa,
    ContratoDetalhamentoItem,
    ContratoItem,
    TermoAditivo,
    DocumentoContrato,
    OcorrenciaContrato,
    OcorrenciaContratoAnexo,
    CompetenciaPagamento,
    ChecklistPagamentoModelo,
    ChecklistPagamentoItem,
    ChecklistPagamentoAnexo,
    MedicaoItemCompetencia,
    ModeloAvaliacaoQualidade,
    GrupoAvaliacaoQualidade,
    CriterioAvaliacaoQualidade,
    AvaliacaoQualidadeCompetencia,
    AvaliacaoCriterioCompetencia,
    EventoFinanceiroContrato,
    EventoFinanceiroItem,
    MemoriaRetroatividade,
]:
    admin.site.register(model)
