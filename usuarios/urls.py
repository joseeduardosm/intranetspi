# Criado por José Eduardo Santana Martins em 04/06/2026
# Define as rotas de ramais, usuários e diretórios LDAP do módulo.
from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
    # Rotas públicas para usuários autenticados e rotas administrativas ficam no mesmo namespace.
    path("ramais/", views.RamaisListView.as_view(), name="ramais"),
    path("usuarios/", views.UsuariosListView.as_view(), name="list"),
    path("usuarios/novo/", views.UsuarioPerfilCreateView.as_view(), name="create"),
    path("usuarios/<int:pk>/editar/", views.UsuarioPerfilUpdateView.as_view(), name="update"),
    path("usuarios/<int:pk>/excluir/", views.UsuarioPerfilDeleteView.as_view(), name="delete"),
    path("diretorios-ldap/", views.LDAPDirectoryListView.as_view(), name="ldap_list"),
    path("diretorios-ldap/novo/", views.LDAPDirectoryCreateView.as_view(), name="ldap_create"),
    path("diretorios-ldap/<int:pk>/editar/", views.LDAPDirectoryUpdateView.as_view(), name="ldap_update"),
    path("diretorios-ldap/<int:pk>/excluir/", views.LDAPDirectoryDeleteView.as_view(), name="ldap_delete"),
]
