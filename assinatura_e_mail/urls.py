from django.urls import path

from . import views

app_name = 'assinatura_e_mail'

urlpatterns = [
    path('', views.AssinaturaEmailView.as_view(), name='form'),
    path('download/', views.AssinaturaEmailDownloadView.as_view(), name='download'),
]
