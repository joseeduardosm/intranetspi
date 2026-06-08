# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Definir o roteamento do módulo Contratos V2 com suas etapas operacionais.

from django.urls import path

from . import views

app_name = 'contratos_v2'

urlpatterns = [
    path('', views.ContratoV2ListView.as_view(), name='contrato_list'),
    path('novo/', views.ContratoV2CreateView.as_view(), name='contrato_create'),
    path('<int:pk>/', views.ContratoV2DetailView.as_view(), name='contrato_detail'),
    path('<int:pk>/editar/', views.ContratoV2UpdateView.as_view(), name='contrato_update'),
    path('<int:pk>/excluir/', views.ContratoV2DeleteView.as_view(), name='contrato_delete'),
    path('<int:contrato_pk>/itens/novo/', views.ContratoItemV2CreateView.as_view(), name='item_create'),
    path('<int:contrato_pk>/itens/<int:pk>/editar/', views.ContratoItemV2UpdateView.as_view(), name='item_update'),
    path('<int:contrato_pk>/itens/<int:pk>/excluir/', views.ContratoItemV2DeleteView.as_view(), name='item_delete'),
    path('<int:contrato_pk>/checklists/novo/', views.ChecklistModeloV2CreateView.as_view(), name='checklist_create'),
    path('checklists/<int:pk>/editar/', views.ChecklistModeloV2UpdateView.as_view(), name='checklist_update'),
    path('checklists/<int:pk>/excluir/', views.ChecklistModeloV2DeleteView.as_view(), name='checklist_delete'),
    path('checklists/<int:modelo_pk>/itens/novo/', views.ChecklistModeloItemV2CreateView.as_view(), name='checklist_item_create'),
    path('checklists/itens/<int:pk>/editar/', views.ChecklistModeloItemV2UpdateView.as_view(), name='checklist_item_update'),
    path('checklists/itens/<int:pk>/excluir/', views.ChecklistModeloItemV2DeleteView.as_view(), name='checklist_item_delete'),
    path('<int:contrato_pk>/avaliacoes/novo/', views.FormularioAvaliacaoV2CreateView.as_view(), name='avaliacao_form_create'),
    path('avaliacoes/<int:pk>/editar/', views.FormularioAvaliacaoV2UpdateView.as_view(), name='avaliacao_form_update'),
    path('avaliacoes/<int:pk>/excluir/', views.FormularioAvaliacaoV2DeleteView.as_view(), name='avaliacao_form_delete'),
    path('avaliacoes/<int:formulario_pk>/escala/nova/', views.EscalaNotaAvaliacaoV2CreateView.as_view(), name='avaliacao_escala_create'),
    path('avaliacoes/escala/<int:pk>/editar/', views.EscalaNotaAvaliacaoV2UpdateView.as_view(), name='avaliacao_escala_update'),
    path('avaliacoes/escala/<int:pk>/excluir/', views.EscalaNotaAvaliacaoV2DeleteView.as_view(), name='avaliacao_escala_delete'),
    path('avaliacoes/<int:formulario_pk>/faixa/nova/', views.FaixaLiberacaoAvaliacaoV2CreateView.as_view(), name='avaliacao_faixa_create'),
    path('avaliacoes/faixa/<int:pk>/editar/', views.FaixaLiberacaoAvaliacaoV2UpdateView.as_view(), name='avaliacao_faixa_update'),
    path('avaliacoes/faixa/<int:pk>/excluir/', views.FaixaLiberacaoAvaliacaoV2DeleteView.as_view(), name='avaliacao_faixa_delete'),
    path('avaliacoes/<int:formulario_pk>/grupo/novo/', views.GrupoAvaliacaoV2CreateView.as_view(), name='avaliacao_grupo_create'),
    path('avaliacoes/grupo/<int:pk>/editar/', views.GrupoAvaliacaoV2UpdateView.as_view(), name='avaliacao_grupo_update'),
    path('avaliacoes/grupo/<int:pk>/excluir/', views.GrupoAvaliacaoV2DeleteView.as_view(), name='avaliacao_grupo_delete'),
    path('avaliacoes/grupo/<int:grupo_pk>/item/novo/', views.ItemAvaliacaoV2CreateView.as_view(), name='avaliacao_item_create'),
    path('avaliacoes/item/<int:pk>/editar/', views.ItemAvaliacaoV2UpdateView.as_view(), name='avaliacao_item_update'),
    path('avaliacoes/item/<int:pk>/excluir/', views.ItemAvaliacaoV2DeleteView.as_view(), name='avaliacao_item_delete'),
    path('<int:contrato_pk>/competencias/gerar/', views.CompetenciasGenerateView.as_view(), name='competencias_generate'),
    path('competencias/<int:competencia_pk>/checklist/', views.CompetenciaChecklistUpdateView.as_view(), name='competencia_checklist'),
    path('competencias/<int:competencia_pk>/medicao/', views.CompetenciaMedicaoUpdateView.as_view(), name='competencia_medicao'),
    path('competencias/<int:competencia_pk>/avaliacao/', views.CompetenciaAvaliacaoUpdateView.as_view(), name='competencia_avaliacao'),
    path('competencias/<int:pk>/pagamento/', views.CompetenciaPagamentoExecuteView.as_view(), name='competencia_pagamento'),
]
