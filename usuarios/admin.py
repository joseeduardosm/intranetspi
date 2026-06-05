# Criado por José Eduardo Santana Martins em 04/06/2026
# Configura a administração de diretórios LDAP e perfis complementares de usuários.
from django.contrib import admin

from .models import LDAPDirectory, UsuarioPerfil


@admin.register(LDAPDirectory)
class LDAPDirectoryAdmin(admin.ModelAdmin):
    """Facilita manutenção e auditoria das configurações LDAP."""

    list_display = ("nome", "host", "port", "use_ssl", "ativo", "atualizado_em")
    list_filter = ("ativo", "use_ssl")
    search_fields = ("nome", "host", "base_dn", "bind_dn")


@admin.register(UsuarioPerfil)
class UsuarioPerfilAdmin(admin.ModelAdmin):
    """Permite consultar dados cadastrais usados em ramais e recadastro."""

    list_display = ("nome_completo", "user", "cargo", "setor", "andar", "bloco", "foto", "ultimo_recadastro_em")
    search_fields = ("nome_completo", "user__username", "cargo", "setor", "andar", "bloco")
