# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Expor as rotas principais do módulo de contratos.

from django.urls import path

from . import views

app_name = 'contratos'

urlpatterns = [
    path('', views.ContratosHomeView.as_view(), name='home'),
    path('empresas/', views.EmpresaListView.as_view(), name='empresa_list'),
    path('empresas/nova/', views.EmpresaCreateView.as_view(), name='empresa_create'),
    path('empresas/<int:pk>/editar/', views.EmpresaUpdateView.as_view(), name='empresa_update'),
    path('empresas/<int:pk>/excluir/', views.EmpresaDeleteView.as_view(), name='empresa_delete'),
    path('empresas/<int:empresa_pk>/responsavel/novo/', views.ResponsavelEmpresaCreateView.as_view(), name='responsavel_create'),
    path('contratos/', views.ContratoListView.as_view(), name='contrato_list'),
    path('contratos/novo/', views.ContratoCreateView.as_view(), name='contrato_create'),
    path('contratos/<int:pk>/', views.ContratoDetailView.as_view(), name='contrato_detail'),
    path('contratos/<int:pk>/editar/', views.ContratoUpdateView.as_view(), name='contrato_update'),
    path('contratos/<int:pk>/excluir/', views.ContratoDeleteView.as_view(), name='contrato_delete'),
    path('contratos/<int:contrato_pk>/item/novo/', views.ContratoItemCreateView.as_view(), name='item_create'),
    path('contratos/<int:contrato_pk>/aditivo/novo/', views.TermoAditivoCreateView.as_view(), name='aditivo_create'),
    path('contratos/<int:contrato_pk>/documento/novo/', views.DocumentoContratoCreateView.as_view(), name='documento_create'),
    path('contratos/<int:contrato_pk>/ocorrencia/nova/', views.OcorrenciaContratoCreateView.as_view(), name='ocorrencia_create'),
    path('ocorrencias/<int:ocorrencia_pk>/anexo/novo/', views.OcorrenciaAnexoCreateView.as_view(), name='ocorrencia_anexo_create'),
    path('contratos/<int:contrato_pk>/competencia/nova/', views.CompetenciaCreateView.as_view(), name='competencia_create'),
    path('competencias/<int:competencia_pk>/checklist-modelo/novo/', views.ChecklistModeloCreateView.as_view(), name='checklist_modelo_create'),
    path('competencias/<int:competencia_pk>/checklist/<int:pk>/concluir/', views.ChecklistItemToggleView.as_view(), name='checklist_item_toggle'),
    path('checklist/<int:item_pk>/anexo/novo/', views.ChecklistAnexoCreateView.as_view(), name='checklist_anexo_create'),
    path('competencias/<int:competencia_pk>/medicao/nova/', views.MedicaoCreateView.as_view(), name='medicao_create'),
    path('competencias/<int:pk>/autorizar/', views.CompetenciaAuthorizeView.as_view(), name='competencia_authorize'),
    path('competencias/<int:competencia_pk>/avaliacao/nova/', views.AvaliacaoCompetenciaCreateView.as_view(), name='avaliacao_create'),
    path('avaliacoes/<int:avaliacao_pk>/criterio/novo/', views.AvaliacaoItemCreateView.as_view(), name='avaliacao_item_create'),
    path('contratos/<int:contrato_pk>/modelo-qualidade/novo/', views.ModeloQualidadeCreateView.as_view(), name='modelo_qualidade_create'),
    path('modelos-qualidade/<int:modelo_pk>/grupo/novo/', views.GrupoQualidadeCreateView.as_view(), name='grupo_qualidade_create'),
    path('grupos-qualidade/<int:grupo_pk>/criterio/novo/', views.CriterioQualidadeCreateView.as_view(), name='criterio_qualidade_create'),
    path('contratos/<int:contrato_pk>/evento-financeiro/novo/', views.EventoFinanceiroCreateView.as_view(), name='evento_create'),
    path('eventos-financeiros/<int:evento_pk>/item/novo/', views.EventoFinanceiroItemCreateView.as_view(), name='evento_item_create'),
    path('contratos/<int:pk>/painel/', views.ContratoDashboardView.as_view(), name='dashboard'),
    path('contratos/<int:pk>/diario/exportar-xlsx/', views.OcorrenciaExportXlsxView.as_view(), name='ocorrencia_export_xlsx'),
]
