# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Mapear as rotas de formulário e download da assinatura de e-mail.

from django.urls import path

from . import views

app_name = 'assinatura_e_mail'

# Rotas do fluxo: gerar prévia no formulário e baixar o PNG assinado.
urlpatterns = [
    path('', views.AssinaturaEmailView.as_view(), name='form'),
    path('download/', views.AssinaturaEmailDownloadView.as_view(), name='download'),
]
