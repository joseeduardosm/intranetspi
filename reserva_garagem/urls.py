# Criado por OpenAI Codex em 17/06/2026
# Define as rotas públicas, administrativas e operacionais do módulo de garagem.

from django.urls import path

from . import views


app_name = "reserva_garagem"

urlpatterns = [
    path("", views.AgendaReservaGaragemView.as_view(), name="agenda"),
    path("dashboard/", views.ReservaGaragemDashboardView.as_view(), name="dashboard"),
    path("reservas/", views.ReservaListView.as_view(), name="reserva_list"),
    path("reservas/vagas-disponiveis/", views.vagas_disponiveis_api, name="vagas_disponiveis"),
    path("reservas/nova/", views.ReservaCreateView.as_view(), name="reserva_create"),
    path("reservas/<int:pk>/", views.ReservaDetailView.as_view(), name="reserva_detail"),
    path("reservas/<int:pk>/editar/", views.ReservaUpdateView.as_view(), name="reserva_update"),
    path("reservas/<int:pk>/cancelar/", views.ReservaCancelView.as_view(), name="reserva_cancel"),
    path("fila-fiscal/", views.FilaFiscalListView.as_view(), name="fila_fiscal"),
    path("fila-fiscal/<int:pk>/analisar/", views.FilaFiscalAnaliseView.as_view(), name="fila_fiscal_analise"),
    path("vagas/", views.VagaListView.as_view(), name="vaga_list"),
    path("vagas/nova/", views.VagaCreateView.as_view(), name="vaga_create"),
    path("vagas/<int:pk>/editar/", views.VagaUpdateView.as_view(), name="vaga_update"),
    path("vagas/<int:pk>/excluir/", views.VagaDeleteView.as_view(), name="vaga_delete"),
    path("configuracao/", views.ConfiguracaoUpdateView.as_view(), name="configuracao"),
]
