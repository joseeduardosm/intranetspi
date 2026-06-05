# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Mapear rotas de imóveis, recursos filhos e eventos processuais.

from django.urls import path

from . import views

app_name = 'regulariza_sgi'

# Rotas organizadas por imóvel, processos SEI, anexos e ações do ciclo atual.
urlpatterns = [
    path('', views.RegularizaSgiHomeView.as_view(), name='home'),
    path('imoveis/', views.ImovelListView.as_view(), name='imovel_list'),
    path('imoveis/novo/', views.ImovelCreateView.as_view(), name='imovel_create'),
    path('imoveis/<int:pk>/', views.ImovelDetailView.as_view(), name='imovel_detail'),
    path('imoveis/<int:pk>/editar/', views.ImovelUpdateView.as_view(), name='imovel_update'),
    path('imoveis/<int:pk>/excluir/', views.ImovelDeleteView.as_view(), name='imovel_delete'),
    path('imoveis/<int:imovel_pk>/sei/novo/', views.ProcessoSEICreateView.as_view(), name='sei_create'),
    path('imoveis/<int:imovel_pk>/sei/<int:pk>/editar/', views.ProcessoSEIUpdateView.as_view(), name='sei_update'),
    path('imoveis/<int:imovel_pk>/sei/<int:pk>/excluir/', views.ProcessoSEIDeleteView.as_view(), name='sei_delete'),
    path('imoveis/<int:imovel_pk>/anexos/novo/', views.AnexoCreateView.as_view(), name='anexo_create'),
    path('imoveis/<int:imovel_pk>/anexos/<int:pk>/editar/', views.AnexoUpdateView.as_view(), name='anexo_update'),
    path('imoveis/<int:imovel_pk>/anexos/<int:pk>/excluir/', views.AnexoDeleteView.as_view(), name='anexo_delete'),
    path('imoveis/<int:pk>/protocolo/', views.RegistrarProtocoloView.as_view(), name='protocolo_create'),
    path('imoveis/<int:pk>/prorrogacao/', views.RegistrarProrrogacaoView.as_view(), name='prorrogacao_create'),
    path('imoveis/<int:pk>/manifestacao/', views.RegistrarManifestacaoView.as_view(), name='manifestacao_create'),
    path('imoveis/<int:pk>/reiniciar-ciclo/', views.ReiniciarCicloView.as_view(), name='reinicio_ciclo'),
]
