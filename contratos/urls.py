# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Definir o roteamento do módulo Contratos V2 com suas etapas operacionais.

from django.urls import path

from . import views

app_name = 'contratos'

urlpatterns = [

    path('empresas/', views.EmpresaListView.as_view(), name='empresa_list'),
    path('empresas/nova/', views.EmpresaCreateView.as_view(), name='empresa_create'),
    path('empresas/<int:pk>/editar/', views.EmpresaUpdateView.as_view(), name='empresa_update'),
    path('empresas/<int:pk>/excluir/', views.EmpresaDeleteView.as_view(), name='empresa_delete'),
    path('empresas/<int:empresa_pk>/responsavel/novo/', views.ResponsavelEmpresaCreateView.as_view(), name='responsavel_create'),

    path('', views.ContratoListView.as_view(), name='contrato_list'),
    path('novo/', views.ContratoCreateView.as_view(), name='contrato_create'),
    path('proximo-numero/', views.proximo_numero_contrato, name='proximo_numero_contrato'),
    path('checklists-padrao/', views.ChecklistPadraoGlobalListView.as_view(), name='checklist_padrao_list'),
    path('checklists-padrao/<int:pk>/', views.ChecklistPadraoGlobalDetailView.as_view(), name='checklist_padrao_detail'),

    path('<int:pk>/', views.ContratoDetailView.as_view(), name='contrato_detail'),
    path('<int:pk>/editar/', views.ContratoUpdateView.as_view(), name='contrato_update'),
    path('<int:pk>/excluir/', views.ContratoDeleteView.as_view(), name='contrato_delete'),
    path('<int:contrato_pk>/itens/novo/', views.ContratoItemCreateView.as_view(), name='item_create'),
    path('<int:contrato_pk>/itens/<int:pk>/editar/', views.ContratoItemUpdateView.as_view(), name='item_update'),
    path('<int:contrato_pk>/itens/<int:pk>/excluir/', views.ContratoItemDeleteView.as_view(), name='item_delete'),
    path('<int:contrato_pk>/documentos/novo/', views.DocumentoImportanteContratoCreateView.as_view(), name='documento_importante_create'),
    path('documentos/<int:pk>/editar/', views.DocumentoImportanteContratoUpdateView.as_view(), name='documento_importante_update'),
    path('documentos/<int:pk>/excluir/', views.DocumentoImportanteContratoDeleteView.as_view(), name='documento_importante_delete'),
    path('checklists-padrao/novo/', views.ChecklistPadraoGlobalCreateView.as_view(), name='checklist_padrao_create'),
    path('checklists-padrao/<int:pk>/editar/', views.ChecklistPadraoGlobalUpdateView.as_view(), name='checklist_padrao_update'),
    path('checklists-padrao/<int:pk>/excluir/', views.ChecklistPadraoGlobalDeleteView.as_view(), name='checklist_padrao_delete'),
    path('checklists-padrao/<int:checklist_padrao_pk>/itens/novo/', views.ChecklistPadraoGlobalItemCreateView.as_view(), name='checklist_padrao_item_create'),
    path('checklists-padrao/itens/<int:pk>/editar/', views.ChecklistPadraoGlobalItemUpdateView.as_view(), name='checklist_padrao_item_update'),
    path('checklists-padrao/itens/<int:pk>/excluir/', views.ChecklistPadraoGlobalItemDeleteView.as_view(), name='checklist_padrao_item_delete'),
    path('<int:contrato_pk>/checklists-padrao/carregar/', views.ChecklistPadraoCarregarView.as_view(), name='checklist_padrao_carregar'),
    path('<int:contrato_pk>/checklists/novo/', views.ChecklistModeloCreateView.as_view(), name='checklist_create'),
    path('checklists/<int:pk>/editar/', views.ChecklistModeloUpdateView.as_view(), name='checklist_update'),
    path('checklists/<int:pk>/excluir/', views.ChecklistModeloDeleteView.as_view(), name='checklist_delete'),
    path('checklists/<int:modelo_pk>/itens/novo/', views.ChecklistModeloItemCreateView.as_view(), name='checklist_item_create'),
    path('checklists/itens/<int:pk>/editar/', views.ChecklistModeloItemUpdateView.as_view(), name='checklist_item_update'),
    path('checklists/itens/<int:pk>/excluir/', views.ChecklistModeloItemDeleteView.as_view(), name='checklist_item_delete'),
    path('<int:contrato_pk>/avaliacoes/novo/', views.FormularioAvaliacaoCreateView.as_view(), name='avaliacao_form_create'),
    path('avaliacoes/<int:pk>/editar/', views.FormularioAvaliacaoUpdateView.as_view(), name='avaliacao_form_update'),
    path('avaliacoes/<int:pk>/excluir/', views.FormularioAvaliacaoDeleteView.as_view(), name='avaliacao_form_delete'),
    path('avaliacoes/<int:formulario_pk>/escala/nova/', views.EscalaNotaAvaliacaoCreateView.as_view(), name='avaliacao_escala_create'),
    path('avaliacoes/escala/<int:pk>/editar/', views.EscalaNotaAvaliacaoUpdateView.as_view(), name='avaliacao_escala_update'),
    path('avaliacoes/escala/<int:pk>/excluir/', views.EscalaNotaAvaliacaoDeleteView.as_view(), name='avaliacao_escala_delete'),
    path('avaliacoes/<int:formulario_pk>/faixa/nova/', views.FaixaLiberacaoAvaliacaoCreateView.as_view(), name='avaliacao_faixa_create'),
    path('avaliacoes/faixa/<int:pk>/editar/', views.FaixaLiberacaoAvaliacaoUpdateView.as_view(), name='avaliacao_faixa_update'),
    path('avaliacoes/faixa/<int:pk>/excluir/', views.FaixaLiberacaoAvaliacaoDeleteView.as_view(), name='avaliacao_faixa_delete'),
    path('avaliacoes/<int:formulario_pk>/grupo/novo/', views.GrupoAvaliacaoCreateView.as_view(), name='avaliacao_grupo_create'),
    path('avaliacoes/grupo/<int:pk>/editar/', views.GrupoAvaliacaoUpdateView.as_view(), name='avaliacao_grupo_update'),
    path('avaliacoes/grupo/<int:pk>/excluir/', views.GrupoAvaliacaoDeleteView.as_view(), name='avaliacao_grupo_delete'),
    path('avaliacoes/grupo/<int:grupo_pk>/item/novo/', views.ItemAvaliacaoCreateView.as_view(), name='avaliacao_item_create'),
    path('avaliacoes/item/<int:pk>/editar/', views.ItemAvaliacaoUpdateView.as_view(), name='avaliacao_item_update'),
    path('avaliacoes/item/<int:pk>/excluir/', views.ItemAvaliacaoDeleteView.as_view(), name='avaliacao_item_delete'),
    path('<int:contrato_pk>/competencias/gerar/', views.CompetenciasGenerateView.as_view(), name='competencias_generate'),
    path('competencias/<int:competencia_pk>/checklist/', views.CompetenciaChecklistUpdateView.as_view(), name='competencia_checklist'),
    path('competencias/<int:competencia_pk>/medicao/', views.CompetenciaMedicaoUpdateView.as_view(), name='competencia_medicao'),
    path('competencias/<int:competencia_pk>/medicao/checklist-extra/novo/', views.CompetenciaChecklistExtraItemCreateView.as_view(), name='competencia_checklist_extra_create'),
    path('competencias/<int:competencia_pk>/avaliacao/', views.CompetenciaAvaliacaoUpdateView.as_view(), name='competencia_avaliacao'),
    path('competencias/<int:competencia_pk>/avaliacao/download/', views.CompetenciaAvaliacaoDownloadView.as_view(), name='competencia_avaliacao_download'),
    path('competencias/<int:pk>/ob/', views.CompetenciaOBExecuteView.as_view(), name='competencia_ob'),
    path('competencias/<int:pk>/pagamento/', views.CompetenciaPagamentoExecuteView.as_view(), name='competencia_pagamento'),
    path('competencias/<int:pk>/download-docs/iniciar/', views.CompetenciaDownloadDocsStartView.as_view(), name='competencia_download_docs_start'),
    path('competencias/download-docs/jobs/<int:job_pk>/status/', views.CompetenciaDownloadDocsStatusView.as_view(), name='competencia_download_docs_status'),
    path('competencias/download-docs/jobs/<int:job_pk>/arquivo/', views.CompetenciaDownloadDocsFileView.as_view(), name='competencia_download_docs_file'),
    path('competencias/<int:pk>/download-docs/', views.CompetenciaDownloadDocsView.as_view(), name='competencia_download_docs'),

    path('<int:contrato_pk>/prazos/novo/', views.PrazoMonitoramentoCreateView.as_view(), name='prazo_create'),
    path('prazos/<int:pk>/editar/', views.PrazoMonitoramentoUpdateView.as_view(), name='prazo_update'),
    path('prazos/<int:pk>/excluir/', views.PrazoMonitoramentoDeleteView.as_view(), name='prazo_delete'),
    path('prazos/<int:pk>/concluir/', views.PrazoMonitoramentoConcluirView.as_view(), name='prazo_concluir'),
]
