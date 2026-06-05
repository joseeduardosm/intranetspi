# Criado por José Eduardo Santana Martins em 04/06/2026
# Concentra regras auxiliares de perfil, usuários técnicos e configuração LDAP.
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import LDAPDirectory, UsuarioPerfil


User = get_user_model()


PROFILE_FIELDS = ("nome_completo", "ramal", "cargo", "setor", "andar", "bloco")
SYSTEM_USERNAMES = {"root"}


def is_system_user(user):
    """Identifica usuários técnicos que não entram nos fluxos comuns de perfil."""

    return bool(user and getattr(user, "username", "").lower() in SYSTEM_USERNAMES)


def is_system_admin(user):
    """Libera administradores do bloqueio de recadastro obrigatório."""

    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))


def ensure_usuario_perfil(user):
    """Garante perfil para o usuário e aproveita nome completo quando disponível."""

    perfil, _created = UsuarioPerfil.objects.get_or_create(user=user)
    if not perfil.nome_completo:
        full_name = (user.get_full_name() or "").strip()
        if full_name:
            perfil.nome_completo = full_name
            perfil.save(update_fields=["nome_completo", "atualizado_em"])
    return perfil


def active_ldap_directory():
    """Retorna o diretório LDAP ativo usado pelo backend de autenticação."""

    return LDAPDirectory.objects.filter(ativo=True).first()


def build_ldap_server(config, Server, NONE, Tls=None):
    """Monta o servidor ldap3 com compatibilidade para SSL legado quando necessário."""

    kwargs = {
        "port": config.port,
        "use_ssl": config.use_ssl,
        "connect_timeout": 5,
        "get_info": NONE,
    }
    if config.use_ssl and Tls:
        import ssl

        kwargs["tls"] = Tls(
            validate=ssl.CERT_NONE,
            version=ssl.PROTOCOL_TLS_CLIENT,
            ciphers="DEFAULT@SECLEVEL=0",
        )
    return Server(config.host, **kwargs)


def profile_update_context(request):
    """Calcula o estado do bloqueio de recadastro usado pelo template base."""

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "usuario_perfil": None,
            "usuario_profile_requires_update": False,
            "usuario_profile_update_allowed": False,
        }
    if is_system_user(user) or is_system_admin(user):
        return {
            "usuario_perfil": None,
            "usuario_profile_requires_update": False,
            "usuario_profile_update_allowed": False,
        }

    perfil = ensure_usuario_perfil(user)
    resolver_match = getattr(request, "resolver_match", None)
    on_own_edit = False
    if resolver_match:
        # O usuário pode acessar a própria tela de edição mesmo quando está bloqueado.
        namespace = getattr(resolver_match, "namespace", "")
        on_own_edit = (
            namespace == "usuarios"
            and getattr(resolver_match, "url_name", "") == "update"
            and str(resolver_match.kwargs.get("pk", "")) == str(perfil.pk)
        )

    return {
        "usuario_perfil": perfil,
        "usuario_profile_requires_update": perfil.precisa_recadastro,
        "usuario_profile_update_allowed": on_own_edit,
        "usuario_profile_reason": "revalidation" if perfil.ultimo_recadastro_em else "missing",
    }


def populate_profile_from_user(perfil):
    """Preenche nome do perfil com dados do User quando ainda estiver vazio."""

    full_name = (perfil.user.get_full_name() or "").strip()
    if full_name and not perfil.nome_completo:
        perfil.nome_completo = full_name
