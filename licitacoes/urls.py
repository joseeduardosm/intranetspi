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
    path('dfd/', views.DfdListView.as_view(), name='dfd_list'),
    path('dfd/novo/', views.DfdCreateView.as_view(), name='dfd_create'),
    path('dfd/<int:pk>/editar/', views.DfdEditView.as_view(), name='dfd_edit'),
    path('dfd/<int:pk>/preview/', views.DfdPreviewView.as_view(), name='dfd_preview'),
    path('dfd/<int:pk>/concluir/', views.DfdConcluirView.as_view(), name='dfd_concluir'),
    path('dfd/<int:pk>/exportar-docx/', views.DfdExportDocxView.as_view(), name='dfd_export'),
    path('dfd/<int:pk>/excluir/', views.DfdDeleteView.as_view(), name='dfd_delete'),
    path('dfd/<int:dfd_pk>/tabela/novo/', views.DfdItemTabelaCreateView.as_view(), name='dfd_tabela_create'),
    path('dfd/<int:dfd_pk>/tabela/<int:pk>/editar/', views.DfdItemTabelaUpdateView.as_view(), name='dfd_tabela_update'),
    path('dfd/<int:dfd_pk>/tabela/<int:pk>/excluir/', views.DfdItemTabelaDeleteView.as_view(), name='dfd_tabela_delete'),
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
    path('sessoes/<int:sessao_pk>/itens/<int:pk>/duplicar/', views.ItemDuplicateView.as_view(), name='item_duplicate'),
    path('sessoes/<int:sessao_pk>/itens/<int:pk>/excluir/', views.ItemDeleteView.as_view(), name='item_delete'),
    path('sessoes/<int:sessao_pk>/itens/<int:item_pk>/tabela/novo/', views.TabelaItemCreateView.as_view(), name='tabela_item_create'),
    path('sessoes/<int:sessao_pk>/itens/<int:item_pk>/tabela/<int:pk>/editar/', views.TabelaItemUpdateView.as_view(), name='tabela_item_update'),
    path('sessoes/<int:sessao_pk>/itens/<int:item_pk>/tabela/<int:pk>/excluir/', views.TabelaItemDeleteView.as_view(), name='tabela_item_delete'),
]
