# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir o roteamento principal e conectar os apps do portal SPI.

"""
URL configuration for aplicacoesspi project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from django.views.generic import RedirectView

from . import views

# View global de acesso negado usada pelas regras de permissão do projeto.
handler403 = 'aplicacoesspi.views.permission_denied_view'

# Roteamento principal que conecta a página inicial, autenticação e os apps do portal.
urlpatterns = [
    path('', views.RootRedirectView.as_view(), name='root'),
    path('login/', views.SuperuserLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.HomeView.as_view(), name='home'),
    path('assinatura-e-mail/', include('assinatura_e_mail.urls')),
    path('atalhos/', include('atalhos.urls')),
    path('contratos/', include('contratos.urls')),
    path('', include('usuarios.urls')),
    path('licitacoes/', include('licitacoes.urls')),
    path('mensageria/', include('mensageria_assincrona.urls')),
    path('navbar/', include('navbar.urls')),
    path('noticias/', include('noticias.urls')),
    path('regulariza-sgi/', include('regulariza_sgi.urls')),
    path('reserva-carros/', include('reserva_carros.urls')),
    path('reserva-garagem/', include('reserva_garagem.urls')),
    # Mantém compatibilidade com links antigos enquanto o módulo passa a usar
    # a URL oficial /reserva-espacos/.
    path('reservas-recursos/', RedirectView.as_view(pattern_name='reserva_espacos:agenda', permanent=False)),
    path('reserva-espacos/', include('reserva_espacos.urls')),
    path('setores/', include('setores.urls')),
    path('acls/', include('acls.urls')),
    path('organograma/', include('organograma.urls')),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    # Em desenvolvimento, o Django entrega arquivos estáticos e mídia diretamente.
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'static')
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
