# Criado por OpenAI Codex em 12/06/2026
# Define as rotas públicas, administrativas e operacionais do módulo de carros.

from django.urls import path

from . import views


app_name = "reserva_carros"

urlpatterns = [
    path("", views.AgendaReservaCarrosView.as_view(), name="agenda"),
    path("dashboard/", views.ReservaCarrosDashboardView.as_view(), name="dashboard"),
    path("solicitacoes/", views.SolicitacaoListView.as_view(), name="solicitacao_list"),
    path("solicitacoes/nova/", views.SolicitacaoCreateView.as_view(), name="solicitacao_create"),
    path("solicitacoes/<int:pk>/", views.SolicitacaoDetailView.as_view(), name="solicitacao_detail"),
    path("solicitacoes/<int:pk>/editar/", views.SolicitacaoUpdateView.as_view(), name="solicitacao_update"),
    path("solicitacoes/<int:pk>/cancelar/", views.SolicitacaoCancelView.as_view(), name="solicitacao_cancel"),
    path("fila-fiscal/", views.FilaFiscalListView.as_view(), name="fila_fiscal"),
    path("fila-fiscal/<int:pk>/analisar/", views.FilaFiscalAnaliseView.as_view(), name="fila_fiscal_analise"),
    path("carros/", views.CarroListView.as_view(), name="carro_list"),
    path("carros/novo/", views.CarroCreateView.as_view(), name="carro_create"),
    path("carros/<int:pk>/editar/", views.CarroUpdateView.as_view(), name="carro_update"),
    path("carros/<int:pk>/excluir/", views.CarroDeleteView.as_view(), name="carro_delete"),
    path("motoristas/", views.MotoristaListView.as_view(), name="motorista_list"),
    path("motoristas/novo/", views.MotoristaCreateView.as_view(), name="motorista_create"),
    path("motoristas/<int:pk>/editar/", views.MotoristaUpdateView.as_view(), name="motorista_update"),
    path("motoristas/<int:pk>/excluir/", views.MotoristaDeleteView.as_view(), name="motorista_delete"),
    path("configuracao/", views.ConfiguracaoUpdateView.as_view(), name="configuracao"),
]
