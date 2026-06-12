"""Rotas do módulo de reservas genéricas."""

from django.urls import path

from . import views


app_name = "reserva_espacos"

urlpatterns = [
    path("", views.AgendaReservaView.as_view(), name="agenda"),
    path("dashboard/", views.ReservaDashboardView.as_view(), name="dashboard"),
    path("dashboard/exportar/", views.reserva_dashboard_exportar, name="dashboard_exportar"),
    path("objetos/", views.ObjetoListView.as_view(), name="objeto_list"),
    path("objetos/novo/", views.ObjetoCreateView.as_view(), name="objeto_create"),
    path("objetos/<int:pk>/editar/", views.ObjetoUpdateView.as_view(), name="objeto_update"),
    path("objetos/<int:pk>/excluir/", views.ObjetoDeleteView.as_view(), name="objeto_delete"),
    path("reservas/", views.ReservaListView.as_view(), name="reserva_list"),
    path("reservas/nova/", views.ReservaCreateView.as_view(), name="reserva_create"),
    path("reservas/<int:pk>/", views.ReservaDetailView.as_view(), name="reserva_detail"),
    path("reservas/<int:pk>/editar/", views.ReservaUpdateView.as_view(), name="reserva_update"),
    path("reservas/<int:pk>/excluir/", views.ReservaDeleteView.as_view(), name="reserva_delete"),
]
