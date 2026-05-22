from django.urls import path

from . import views

app_name = 'noticias'

urlpatterns = [
    path('', views.NoticiaPublicListView.as_view(), name='public_list'),
    path('todas/', views.NoticiaArchiveView.as_view(), name='archive'),
    path('<int:pk>/', views.NoticiaPublicDetailView.as_view(), name='public_detail'),
    path('<int:pk>/pdf/', views.NoticiaPdfView.as_view(), name='pdf'),
    path('gerenciar/', views.NoticiaManageListView.as_view(), name='manage_list'),
    path('gerenciar/nova/', views.NoticiaCreateView.as_view(), name='create'),
    path('gerenciar/<int:pk>/editar/', views.NoticiaUpdateView.as_view(), name='update'),
    path('gerenciar/<int:pk>/duplicar/', views.NoticiaDuplicateView.as_view(), name='duplicate'),
    path('gerenciar/<int:pk>/publicar/', views.NoticiaPublicarView.as_view(), name='publish'),
    path('gerenciar/<int:pk>/rascunhar/', views.NoticiaRascunharView.as_view(), name='draft'),
    path('gerenciar/<int:pk>/excluir/', views.NoticiaDeleteView.as_view(), name='delete'),
]
