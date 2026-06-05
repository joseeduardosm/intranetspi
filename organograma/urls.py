# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Mapear a rota principal de visualização do organograma.

from django.urls import path

from . import views

app_name = 'organograma'

# Rota única do módulo, responsável por exibir a árvore institucional.
urlpatterns = [
    path('', views.SetorOrganogramaView.as_view(), name='organograma'),
]
