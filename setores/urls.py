# Criado por José Eduardo Santana Martins em 04/06/2026
# Define as rotas do módulo de setores para painel, listagem e CRUD.
from django.urls import path

from . import views

app_name = 'setores'

urlpatterns = [
    # As URLs separam a entrada do módulo da manutenção administrativa.
    path('', views.SetoresHomeView.as_view(), name='home'),
    path('lista/', views.SetorListView.as_view(), name='list'),
    path('novo/', views.SetorCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', views.SetorUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.SetorDeleteView.as_view(), name='delete'),
]
