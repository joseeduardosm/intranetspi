# Criado por José Eduardo Santana Martins em 04/06/2026
# Implementa autenticação LDAP e sincroniza dados básicos do usuário autenticado.
import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

from .services import active_ldap_directory, build_ldap_server, ensure_usuario_perfil


logger = logging.getLogger(__name__)
UserModel = get_user_model()


class LDAPBackend(BaseBackend):
    """Backend de autenticação corporativa com fallback de bind por DN, UPN e NTLM."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        config = active_ldap_directory()
        if not config:
            return None

        try:
            from ldap3 import Connection, NTLM, NONE, SUBTREE, Server, Tls
            from ldap3.core.exceptions import LDAPBindError
        except Exception:
            return None

        server = build_ldap_server(config, Server, NONE, Tls)
        try:
            connection = Connection(
                server,
                user=config.bind_dn,
                password=config.bind_password,
                auto_bind=True,
            )
        except Exception as exc:
            logger.warning("LDAP bind de servico falhou: %s", exc)
            return None

        try:
            search_filter = (
                f"(userPrincipalName={username})"
                if "@" in username
                else f"(sAMAccountName={username})"
            )
            # Primeiro o bind de serviço localiza o usuário dentro da base configurada.
            connection.search(
                search_base=config.base_dn,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=[
                    "distinguishedName",
                    "givenName",
                    "sn",
                    "displayName",
                    "mail",
                    "sAMAccountName",
                ],
            )
            if not connection.entries:
                return None

            entry = connection.entries[0]
            user_dn = str(entry.distinguishedName)
            try:
                # A senha informada só é aceita após bind real com a identidade do usuário.
                self._bind_user(server, config.base_dn, username, password, user_dn, Connection, LDAPBindError, NTLM)
            except LDAPBindError as exc:
                logger.warning("LDAP credenciais invalidas para %s: %s", username, exc)
                return None

            username_value = str(entry.sAMAccountName) if entry.sAMAccountName else username
            email_value = str(entry.mail) if entry.mail else ""
            display_name = str(entry.displayName) if entry.displayName else ""
            given_name = str(entry.givenName) if entry.givenName else ""
            surname = str(entry.sn) if entry.sn else ""

            defaults = {
                "email": email_value,
                "first_name": given_name or display_name or username_value,
                "last_name": surname,
                "is_active": True,
                "is_staff": False,
                "is_superuser": False,
            }
            user, created = UserModel.objects.get_or_create(username=username_value, defaults=defaults)
            if created:
                # Usuários LDAP não recebem senha local utilizável.
                user.set_unusable_password()
                user.save(update_fields=["password"])
            else:
                update_fields = []
                if email_value and email_value != user.email:
                    user.email = email_value
                    update_fields.append("email")
                if given_name and given_name != user.first_name:
                    user.first_name = given_name
                    update_fields.append("first_name")
                if surname != user.last_name:
                    user.last_name = surname
                    update_fields.append("last_name")
                if not user.is_active:
                    user.is_active = True
                    update_fields.append("is_active")
                if update_fields:
                    user.save(update_fields=update_fields)

            perfil = ensure_usuario_perfil(user)
            # Mantém o nome exibido nos ramais alinhado ao diretório corporativo.
            full_name = display_name or " ".join(part for part in [given_name, surname] if part).strip() or username_value
            if perfil.nome_completo != full_name:
                perfil.nome_completo = full_name
                perfil.save(update_fields=["nome_completo", "atualizado_em"])
            return user
        finally:
            connection.unbind()

    def _bind_user(self, server, base_dn, username, password, user_dn, Connection, LDAPBindError, NTLM):
        """Tenta autenticar por DN e recorre a UPN/NTLM para ambientes Active Directory."""

        try:
            user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
            user_conn.unbind()
            return
        except LDAPBindError as dn_exc:
            domain_parts = [
                part.split("=", 1)[1]
                for part in base_dn.split(",")
                if part.strip().lower().startswith("dc=")
            ]
            if domain_parts:
                upn = f"{username}@{'.'.join(domain_parts)}"
                try:
                    user_conn = Connection(server, user=upn, password=password, auto_bind=True)
                    user_conn.unbind()
                    return
                except LDAPBindError as upn_exc:
                    domain = domain_parts[0]
                    try:
                        user_conn = Connection(
                            server,
                            user=f"{domain}\\{username}",
                            password=password,
                            authentication=NTLM,
                            auto_bind=True,
                        )
                        user_conn.unbind()
                        return
                    except LDAPBindError as ntlm_exc:
                        logger.warning("LDAP bind falhou (DN/UPN/NTLM): %s | %s | %s", dn_exc, upn_exc, ntlm_exc)
                        raise ntlm_exc
            raise dn_exc

    def get_user(self, user_id):
        """Recupera usuário autenticado para a sessão Django."""

        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
