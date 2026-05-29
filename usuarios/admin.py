from django.contrib import admin

from .models import LDAPDirectory, UsuarioPerfil


@admin.register(LDAPDirectory)
class LDAPDirectoryAdmin(admin.ModelAdmin):
    list_display = ("nome", "host", "port", "use_ssl", "ativo", "atualizado_em")
    list_filter = ("ativo", "use_ssl")
    search_fields = ("nome", "host", "base_dn", "bind_dn")


@admin.register(UsuarioPerfil)
class UsuarioPerfilAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "user", "cargo", "setor", "andar", "bloco", "foto", "ultimo_recadastro_em")
    search_fields = ("nome_completo", "user__username", "cargo", "setor", "andar", "bloco")
