# Criado por José Eduardo Santana Martins em 04/06/2026

from django.urls import path
from . import views

app_name = 'acls'

# Rotas administrativas para listar, criar, editar e remover regras de acesso.
urlpatterns = [
    path('', views.ACLRuleListView.as_view(), name='list'),
    path('nova/', views.ACLRuleCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', views.ACLRuleUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.ACLRuleDeleteView.as_view(), name='delete'),
]
