# Criado por OpenAI Codex em 12/06/2026
# Define as rotas públicas e administrativas do módulo de mensageria.

from django.urls import path

from . import views


app_name = "mensageria"

urlpatterns = [
    path("", views.MensagemAdminListView.as_view(), name="root"),
    path("minhas/", views.MinhasMensagensListView.as_view(), name="minhas"),
    path("minhas/<int:pk>/", views.MinhaMensagemDetailView.as_view(), name="minha_detail"),
    path("admin/", views.MensagemAdminListView.as_view(), name="admin_list"),
    path("admin/nova/", views.MensagemAdminCreateView.as_view(), name="admin_create"),
    path("admin/<int:pk>/", views.MensagemAdminDetailView.as_view(), name="admin_detail"),
    path("admin/<int:pk>/editar/", views.MensagemAdminUpdateView.as_view(), name="admin_update"),
    path("admin/<int:pk>/cancelar/", views.MensagemCancelarView.as_view(), name="admin_cancel"),
    path("ciente/", views.MensagemCienteView.as_view(), name="ciente"),
    path("visualizada/", views.MensagemVisualizadaView.as_view(), name="visualizada"),
    path("indicadores/", views.MensageriaIndicadoresView.as_view(), name="indicadores"),
]
