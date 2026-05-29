from django.urls import path

from . import views


app_name = "usuarios"

urlpatterns = [
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
