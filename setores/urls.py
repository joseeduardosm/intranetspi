from django.urls import path

from . import views

app_name = 'setores'

urlpatterns = [
    path('', views.SetoresHomeView.as_view(), name='home'),
    path('lista/', views.SetorListView.as_view(), name='list'),
    path('novo/', views.SetorCreateView.as_view(), name='create'),
    path('<int:pk>/editar/', views.SetorUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.SetorDeleteView.as_view(), name='delete'),
]
