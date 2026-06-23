# Criado por OpenAI Codex em 19/06/2026
# Objetivo: Mapear as rotas do backlog técnico simplificado.

from django.urls import path

from . import views


app_name = "todo_tecnico"

urlpatterns = [
    path("", views.TarefaTecnicaListView.as_view(), name="list"),
    path("nova/", views.TarefaTecnicaCreateView.as_view(), name="create"),
    path("codex/configuracao/", views.CodexConfiguracaoUpdateView.as_view(), name="codex_config"),
    path("<int:pk>/", views.TarefaTecnicaDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", views.TarefaTecnicaUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", views.TarefaExcluirView.as_view(), name="delete"),
    path("<int:pk>/solucionar/", views.TarefaTecnicaSolucionarView.as_view(), name="solve"),
    path("<int:pk>/reabrir/", views.TarefaReabrirView.as_view(), name="reopen"),
    path("<int:pk>/codex/executar/", views.TarefaCodexExecutarView.as_view(), name="codex_run"),
    path("<int:pk>/codex/agendar/", views.TarefaCodexAgendarView.as_view(), name="codex_schedule"),
]
