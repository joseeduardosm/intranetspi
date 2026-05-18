from django.urls import path

from . import views

app_name = 'licitacoes'

urlpatterns = [
    path('', views.LicitacoesHomeView.as_view(), name='home'),
    path('etp-tic/', views.EtpTicListView.as_view(), name='etp_list'),
    path('etp-tic/novo/', views.EtpTicCreateView.as_view(), name='etp_create'),
    path('etp-tic/<int:pk>/editar/', views.EtpTicEditView.as_view(), name='etp_edit'),
    path('etp-tic/<int:pk>/preview/', views.EtpTicPreviewView.as_view(), name='etp_preview'),
    path('etp-tic/<int:pk>/concluir/', views.EtpTicConcluirView.as_view(), name='etp_concluir'),
    path('etp-tic/<int:pk>/exportar-docx/', views.EtpTicExportDocxView.as_view(), name='etp_export'),
    path('etp-tic/<int:pk>/excluir/', views.EtpTicDeleteView.as_view(), name='etp_delete'),
    path('tr/', views.TermoListView.as_view(), name='tr_list'),
    path('tr/novo/', views.TermoCreateView.as_view(), name='tr_create'),
    path('tr/<int:pk>/', views.TermoDetailView.as_view(), name='tr_detail'),
    path('tr/<int:pk>/editar/', views.TermoUpdateView.as_view(), name='tr_update'),
    path('tr/<int:pk>/exportar-docx/', views.TermoExportDocxView.as_view(), name='tr_export'),
    path('tr/<int:pk>/excluir/', views.TermoDeleteView.as_view(), name='tr_delete'),
    path('tr/<int:termo_pk>/sessoes/nova/', views.SessaoCreateView.as_view(), name='sessao_create'),
    path('tr/<int:termo_pk>/sessoes/<int:pk>/editar/', views.SessaoUpdateView.as_view(), name='sessao_update'),
    path('tr/<int:termo_pk>/sessoes/<int:pk>/excluir/', views.SessaoDeleteView.as_view(), name='sessao_delete'),
    path('sessoes/<int:sessao_pk>/itens/novo/', views.ItemCreateView.as_view(), name='item_create'),
    path('sessoes/<int:sessao_pk>/itens/<int:parent_pk>/subitem/novo/', views.ItemCreateView.as_view(), name='item_child_create'),
    path('sessoes/<int:sessao_pk>/itens/<int:pk>/editar/', views.ItemUpdateView.as_view(), name='item_update'),
    path('sessoes/<int:sessao_pk>/itens/<int:pk>/mover/', views.ItemMoveView.as_view(), name='item_move'),
    path('sessoes/<int:sessao_pk>/itens/<int:pk>/excluir/', views.ItemDeleteView.as_view(), name='item_delete'),
]
