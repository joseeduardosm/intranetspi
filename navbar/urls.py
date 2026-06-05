from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'navbar'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='navbar:manage_list'), name='home'),
    path('gerenciar/', views.NavbarItemListView.as_view(), name='manage_list'),
    path('gerenciar/novo/', views.NavbarItemCreateView.as_view(), name='create'),
    path('gerenciar/<int:pk>/mover/', views.NavbarItemMoveView.as_view(), name='move'),
    path('gerenciar/<int:pk>/editar/', views.NavbarItemUpdateView.as_view(), name='update'),
    path('gerenciar/<int:pk>/excluir/', views.NavbarItemDeleteView.as_view(), name='delete'),
]
