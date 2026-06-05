from django.urls import path
from . import views

app_name = 'acls'

urlpatterns = [
    path('', views.ACLRuleListView.as_view(), name='list'),
    path('nova/', views.ACLRuleCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', views.ACLRuleUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.ACLRuleDeleteView.as_view(), name='delete'),
]
