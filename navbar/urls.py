# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Mapear as rotas administrativas de gestão da navbar.

from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'navbar'

# Rotas de gerenciamento: listar, criar, mover, editar e excluir itens do menu.
urlpatterns = [
    path('', RedirectView.as_view(pattern_name='navbar:manage_list'), name='home'),
    path('gerenciar/', views.NavbarItemListView.as_view(), name='manage_list'),
    path('gerenciar/novo/', views.NavbarItemCreateView.as_view(), name='create'),
    path('gerenciar/<int:pk>/mover/', views.NavbarItemMoveView.as_view(), name='move'),
    path('gerenciar/<int:pk>/editar/', views.NavbarItemUpdateView.as_view(), name='update'),
    path('gerenciar/<int:pk>/excluir/', views.NavbarItemDeleteView.as_view(), name='delete'),
]
