from django.urls import path

from . import views

app_name = 'organograma'

urlpatterns = [
    path('', views.SetorOrganogramaView.as_view(), name='organograma'),
]
