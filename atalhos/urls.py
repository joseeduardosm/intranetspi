# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Mapear as rotas administrativas de listagem, criação, edição e exclusão.

from django.urls import path

from . import views

app_name = 'atalhos'

# Rotas do CRUD de atalhos usado por superusuários.
urlpatterns = [
    path('', views.AtalhoListView.as_view(), name='manage_list'),
    path('novo/', views.AtalhoCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', views.AtalhoUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.AtalhoDeleteView.as_view(), name='delete'),
]
