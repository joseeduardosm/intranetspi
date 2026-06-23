# Criado por OpenAI Codex em 23/06/2026
# Define as rotas HTML do módulo de tarefas no padrão atual do portal.

from django.urls import path

from .views import (
    TarefaCreateView,
    TarefaDetailView,
    TarefaHistoricoCreateView,
    TarefaListView,
    TarefaPrazoUpdateView,
    TarefaStatusUpdateView,
    TarefaUpdateView,
    TarefasPessoaGerencialView,
    TarefasOnboardingView,
)


app_name = "tarefas"


urlpatterns = [
    path("", TarefaListView.as_view(), name="list"),
    path("primeiro-acesso/", TarefasOnboardingView.as_view(), name="onboarding"),
    path("nova/", TarefaCreateView.as_view(), name="create"),
    path("equipe/pessoa/<int:user_id>/", TarefasPessoaGerencialView.as_view(), name="team_person"),
    path("<int:pk>/", TarefaDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", TarefaUpdateView.as_view(), name="update"),
    path("<int:pk>/prazo/", TarefaPrazoUpdateView.as_view(), name="update_prazo"),
    path("<int:pk>/status/", TarefaStatusUpdateView.as_view(), name="update_status"),
    path("<int:pk>/historico/novo/", TarefaHistoricoCreateView.as_view(), name="historico_create"),
]
