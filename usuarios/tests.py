# Criado por José Eduardo Santana Martins em 04/06/2026
# Cobre perfis, ramais, LDAP, permissões e recadastro obrigatório do app usuários.
from io import BytesIO
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from setores.models import SetorNode, UserSetorMembership
from .backends import LDAPBackend
from .models import LDAPDirectory, UsuarioPerfil
from .context_processors import usuario_profile_state
from .services import profile_update_context


User = get_user_model()


def foto_upload(name="foto.png"):
    """Gera uma imagem mínima em memória para validações de upload."""

    buffer = BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class UsuariosTests(TestCase):
    """Valida fluxos de cadastro, listagem, recadastro e diretórios LDAP."""

    def setUp(self):
        self.admin = User.objects.create_superuser(username="admin", password="123", email="admin@example.com")
        self.user = User.objects.create_user(username="joao", password="123", email="joao@example.com")
        self.setor_ti = SetorNode.objects.create(group=Group.objects.create(name="TI"))
        self.setor_rh = SetorNode.objects.create(group=Group.objects.create(name="RH"))

    def test_cria_perfil_automaticamente_ao_criar_usuario(self):
        self.assertTrue(UsuarioPerfil.objects.filter(user=self.user).exists())

    def test_login_local_superuser_permanece_funcional(self):
        response = self.client.post(reverse("login"), {"username": "admin", "password": "123"})
        self.assertRedirects(response, reverse("root"), fetch_redirect_response=False)

    def test_home_exibe_modal_bloqueante_quando_cadastro_incompleto(self):
        self.client.login(username="joao", password="123")
        response = self.client.get(reverse("noticias:public_list"))
        self.assertContains(response, "Atualize seus dados antes de continuar")
        self.assertContains(response, reverse("usuarios:update", args=[self.user.perfil.pk]))

    def test_contexto_nao_exige_recadastro_com_campos_completos_e_data_recente(self):
        perfil = self.user.perfil
        perfil.nome_completo = "Joao Silva"
        perfil.ramal = "1234"
        perfil.cargo = "Analista"
        perfil.setor = "TI"
        perfil.andar = "3"
        perfil.bloco = "A"
        perfil.foto = "usuarios/fotos/joao.png"
        perfil.ultimo_recadastro_em = perfil.atualizado_em
        perfil.save()
        request = RequestFactory().get("/noticias/")
        request.user = self.user
        request.resolver_match = SimpleNamespace(namespace="noticias", url_name="public_list", kwargs={})
        context = profile_update_context(request)
        self.assertFalse(context["usuario_profile_requires_update"])

    def test_usuario_root_nao_exige_recadastro(self):
        root = User.objects.create_superuser(username="root", password="123")
        request = RequestFactory().get("/noticias/")
        request.user = root
        request.resolver_match = SimpleNamespace(namespace="noticias", url_name="public_list", kwargs={})
        context = profile_update_context(request)
        self.assertFalse(context["usuario_profile_requires_update"])
        self.assertIsNone(context["usuario_perfil"])

    def test_administrador_do_sistema_nao_fica_bloqueado_por_recadastro(self):
        request = RequestFactory().get("/noticias/")
        request.user = self.admin
        request.resolver_match = SimpleNamespace(namespace="noticias", url_name="public_list", kwargs={})

        context = profile_update_context(request)

        self.assertFalse(context["usuario_profile_requires_update"])
        self.assertIsNone(context["usuario_perfil"])

    def test_contexto_libera_tela_de_edicao_do_proprio_cadastro(self):
        request = RequestFactory().get(reverse("usuarios:update", args=[self.user.perfil.pk]))
        request.user = self.user
        request.resolver_match = SimpleNamespace(
            namespace="usuarios",
            url_name="update",
            kwargs={"pk": self.user.perfil.pk},
        )
        context = profile_update_context(request)
        self.assertTrue(context["usuario_profile_requires_update"])
        self.assertTrue(context["usuario_profile_update_allowed"])

    def test_contexto_de_aniversariantes_entrega_dados_do_cartao_de_contato(self):
        self.user.perfil.nome_completo = "Joao Silva"
        self.user.perfil.ramal = "4321"
        self.user.perfil.celular = "(11) 99999-1111"
        self.user.perfil.cargo = "Analista"
        self.user.perfil.setor = "TI"
        self.user.perfil.andar = "4"
        self.user.perfil.bloco = "A"
        self.user.perfil.data_nascimento = timezone.localdate().replace(day=1)
        self.user.perfil.foto = "usuarios/fotos/joao.png"
        self.user.perfil.save()

        request = RequestFactory().get("/noticias/")
        request.user = self.user
        request.resolver_match = SimpleNamespace(namespace="noticias", url_name="public_list", kwargs={})

        context = usuario_profile_state(request)

        self.assertEqual(len(context["aniversariantes"]), 1)
        aniversariante = context["aniversariantes"][0]
        self.assertEqual(aniversariante["nome"], "Joao Silva")
        self.assertEqual(aniversariante["cargo"], "Analista")
        self.assertEqual(aniversariante["setor"], "TI")
        self.assertEqual(aniversariante["email"], "joao@example.com")
        self.assertEqual(aniversariante["ramal"], "4321")
        self.assertEqual(aniversariante["local"], "4 Andar - Bloco A")
        self.assertTrue(aniversariante["foto_url"].endswith("usuarios/fotos/joao.png"))

    def test_lista_ramais_busca_e_ordena_no_queryset(self):
        outro = User.objects.create_user(username="maria", password="123")
        perfil_outro = outro.perfil
        perfil_outro.nome_completo = "Maria Souza"
        perfil_outro.ramal = "2211"
        perfil_outro.user.email = "maria@spi.local"
        perfil_outro.user.save(update_fields=["email"])
        perfil_outro.cargo = "Coordenadora"
        perfil_outro.setor = "RH"
        perfil_outro.andar = "2"
        perfil_outro.bloco = "B"
        perfil_outro.foto = "usuarios/fotos/maria.png"
        perfil_outro.save()

        perfil = self.user.perfil
        perfil.nome_completo = "Joao Silva"
        perfil.ramal = "4321"
        perfil.user.email = "joao@spi.local"
        perfil.user.save(update_fields=["email"])
        perfil.cargo = "Analista"
        perfil.setor = "TI"
        perfil.andar = "4"
        perfil.bloco = "A"
        perfil.foto = "usuarios/fotos/joao.png"
        perfil.save()

        self.client.login(username="joao", password="123")
        response = self.client.get(reverse("usuarios:ramais"), {"q": "RH", "sort": "email", "dir": "asc"})
        self.assertContains(response, "Maria Souza")
        self.assertNotContains(response, "Joao Silva")

    def test_lista_ramais_nao_exibe_usuario_root(self):
        root = User.objects.create_superuser(username="root", password="123")
        root.perfil.nome_completo = "Root"
        root.perfil.cargo = "Sistema"
        root.perfil.setor = "TI"
        root.perfil.andar = "1"
        root.perfil.bloco = "A"
        root.perfil.foto = "usuarios/fotos/root.png"
        root.perfil.save()

        perfil = self.user.perfil
        perfil.nome_completo = "Joao Silva"
        perfil.ramal = "4321"
        perfil.cargo = "Analista"
        perfil.setor = "TI"
        perfil.andar = "4"
        perfil.bloco = "A"
        perfil.foto = "usuarios/fotos/joao.png"
        perfil.save()

        self.client.login(username="joao", password="123")
        response = self.client.get(reverse("usuarios:ramais"))
        self.assertContains(response, "Joao Silva")
        self.assertNotContains(response, "Root")

    def test_lista_ramais_exibe_apenas_cadastros_completos(self):
        completo = self.user.perfil
        completo.nome_completo = "Joao Silva"
        completo.ramal = "4321"
        completo.cargo = "Analista"
        completo.setor = "TI"
        completo.andar = "4"
        completo.bloco = "A"
        completo.foto = "usuarios/fotos/joao.png"
        completo.save()

        incompleto = User.objects.create_user(username="maria", password="123", email="maria@spi.local")
        incompleto.perfil.nome_completo = "Maria Souza"
        incompleto.perfil.cargo = "Coordenadora"
        incompleto.perfil.setor = "RH"
        incompleto.perfil.andar = "2"
        incompleto.perfil.bloco = "B"
        incompleto.perfil.foto = "usuarios/fotos/maria.png"
        incompleto.perfil.save()

        self.client.login(username="joao", password="123")
        response = self.client.get(reverse("usuarios:ramais"))

        self.assertContains(response, "Joao Silva")
        self.assertNotContains(response, "Maria Souza")

    def test_admin_ve_botao_de_novo_usuario_na_listagem(self):
        self.client.login(username="admin", password="123")
        response = self.client.get(reverse("usuarios:list"))
        self.assertContains(response, reverse("usuarios:create"))

    def test_lista_usuarios_pagina_dez_por_vez(self):
        for idx in range(11):
            user = User.objects.create_user(username=f"user{idx:02d}", password="123")
            perfil = user.perfil
            perfil.nome_completo = f"Usuario {idx:02d}"
            perfil.save()

        self.client.login(username="admin", password="123")

        response = self.client.get(reverse("usuarios:list"))
        page_2_response = self.client.get(f"{reverse('usuarios:list')}?page=2")

        self.assertEqual(len(response.context["perfis"]), 10)
        self.assertContains(response, "Página 1 de 2")
        self.assertEqual(len(page_2_response.context["perfis"]), 3)
        self.assertContains(page_2_response, "Página 2 de 2")

    def test_admin_pode_criar_novo_usuario(self):
        self.client.login(username="admin", password="123")
        response = self.client.post(
            reverse("usuarios:create"),
            {
                "login": "maria",
                "password1": "senha-forte-123",
                "password2": "senha-forte-123",
                "nome_completo": "Maria Souza",
                "email": "maria@spi.local",
                "ramal": "5544",
                "foto": foto_upload(),
                "cargo": "Coordenadora",
                "setor": str(self.setor_rh.pk),
                "andar": "2",
                "bloco": "B",
            },
        )
        self.assertRedirects(response, reverse("usuarios:list"), fetch_redirect_response=False)
        user = User.objects.get(username="maria")
        self.assertEqual(user.email, "maria@spi.local")
        self.assertTrue(UsuarioPerfil.objects.filter(user=user, nome_completo="Maria Souza", ramal="5544").exists())
        self.assertTrue(UserSetorMembership.objects.filter(user=user, setor=self.setor_rh).exists())

    def test_admin_nao_cria_usuario_sem_ramal(self):
        self.client.login(username="admin", password="123")
        response = self.client.post(
            reverse("usuarios:create"),
            {
                "login": "maria",
                "password1": "senha-forte-123",
                "password2": "senha-forte-123",
                "nome_completo": "Maria Souza",
                "email": "maria@spi.local",
                "foto": foto_upload(),
                "cargo": "Coordenadora",
                "setor": str(self.setor_rh.pk),
                "andar": "2",
                "bloco": "B",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "ramal", "Este campo é obrigatório.")
        self.assertFalse(User.objects.filter(username="maria").exists())

    def test_usuario_comum_nao_pode_criar_novo_usuario(self):
        self.client.login(username="joao", password="123")
        response = self.client.get(reverse("usuarios:create"))
        self.assertEqual(response.status_code, 403)

    def test_form_usuario_exibe_combobox_de_setores(self):
        self.client.login(username="admin", password="123")
        response = self.client.get(reverse("usuarios:create"))
        self.assertContains(response, '<select name="setor"', html=False)
        self.assertContains(response, "TI")
        self.assertContains(response, "RH")

    def test_usuario_comum_edita_apenas_o_proprio_cadastro(self):
        outro = User.objects.create_user(username="maria", password="123")
        self.client.login(username="joao", password="123")
        response = self.client.get(reverse("usuarios:update", args=[outro.perfil.pk]))
        self.assertEqual(response.status_code, 403)

    def test_tela_de_edicao_do_proprio_cadastro_nao_renderiza_modal_bloqueante(self):
        self.client.login(username="joao", password="123")
        response = self.client.get(reverse("usuarios:update", args=[self.user.perfil.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Atualize seus dados antes de continuar")

    def test_admin_pode_promover_e_rebaixar_usuario(self):
        perfil = self.user.perfil
        self.client.login(username="admin", password="123")
        response = self.client.post(
            reverse("usuarios:update", args=[perfil.pk]),
            {
                "nome_completo": "Joao Silva",
                "email": "joao@spi.local",
                "ramal": "1234",
                "foto": foto_upload(),
                "cargo": "Analista",
                "setor": str(self.setor_ti.pk),
                "andar": "3",
                "bloco": "A",
                "administrador_sistema": "on",
            },
        )
        self.assertRedirects(response, reverse("usuarios:list"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_superuser)
        self.assertTrue(self.user.is_staff)
        self.assertEqual(self.user.email, "joao@spi.local")
        self.assertEqual(perfil.user.email, "joao@spi.local")

    def test_cadastro_salva_email_e_ramal(self):
        perfil = self.user.perfil
        self.client.login(username="joao", password="123")
        response = self.client.post(
            reverse("usuarios:update", args=[perfil.pk]),
            {
                "nome_completo": "Joao Silva",
                "email": "joao.silva@spi.local",
                "ramal": "9988",
                "foto": foto_upload(),
                "cargo": "Analista",
                "setor": str(self.setor_ti.pk),
                "andar": "3",
                "bloco": "A",
            },
        )
        self.assertRedirects(response, reverse("usuarios:ramais"), fetch_redirect_response=False)
        perfil.refresh_from_db()
        self.assertEqual(perfil.ramal, "9988")
        self.assertEqual(perfil.user.email, "joao.silva@spi.local")

    def test_usuario_incompleto_e_excluido_ao_sair_sem_finalizar_primeiro_cadastro(self):
        self.client.login(username="joao", password="123")

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("noticias:public_list"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_usuario_ja_cadastrado_nao_e_excluido_ao_sair(self):
        perfil = self.user.perfil
        perfil.nome_completo = "Joao Silva"
        perfil.ramal = "9988"
        perfil.cargo = "Analista"
        perfil.setor = "TI"
        perfil.andar = "3"
        perfil.bloco = "A"
        perfil.foto = "usuarios/fotos/joao.png"
        perfil.ultimo_recadastro_em = perfil.atualizado_em
        perfil.save()

        self.client.login(username="joao", password="123")
        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("noticias:public_list"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_admin_pode_excluir_usuario(self):
        perfil = self.user.perfil
        self.client.login(username="admin", password="123")
        response = self.client.post(reverse("usuarios:delete", args=[perfil.pk]))
        self.assertRedirects(response, reverse("usuarios:list"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_diretorio_ldap_ativo_deve_ser_unico(self):
        LDAPDirectory.objects.create(
            nome="Primario",
            host="ldap1",
            port=389,
            use_ssl=False,
            base_dn="dc=example,dc=com",
            bind_dn="cn=svc",
            bind_password="123",
            ativo=True,
        )
        directory = LDAPDirectory(
            nome="Secundario",
            host="ldap2",
            port=389,
            use_ssl=False,
            base_dn="dc=example,dc=com",
            bind_dn="cn=svc",
            bind_password="123",
            ativo=True,
        )
        with self.assertRaises(ValidationError):
            directory.full_clean()

    def test_crud_diretorio_ldap(self):
        self.client.login(username="admin", password="123")
        response = self.client.post(
            reverse("usuarios:ldap_create"),
            {
                "nome": "Primario",
                "host": "ldap1",
                "port": "389",
                "base_dn": "dc=example,dc=com",
                "bind_dn": "cn=svc",
                "bind_password": "123",
                "ativo": "on",
            },
        )
        self.assertRedirects(response, reverse("usuarios:ldap_list"), fetch_redirect_response=False)
        self.assertTrue(LDAPDirectory.objects.filter(nome="Primario").exists())


class LDAPBackendTests(TestCase):
    """Isola o backend LDAP com módulos falsos para cobrir os fallbacks de bind."""

    def setUp(self):
        LDAPDirectory.objects.create(
            nome="Primario",
            host="ldap1",
            port=389,
            use_ssl=False,
            base_dn="dc=example,dc=com",
            bind_dn="cn=svc",
            bind_password="123",
            ativo=True,
        )

    def _fake_ldap_modules(self, accepted_users, mail="joao@example.com"):
        """Monta módulos ldap3 falsos e registra tentativas de autenticação."""

        attempts = []

        class LDAPBindError(Exception):
            pass

        class FakeConnection:
            def __init__(self, server, user, password, auto_bind=True, authentication=None):
                attempts.append(user)
                if user == "cn=svc":
                    self.entries = []
                    return
                if user not in accepted_users:
                    raise LDAPBindError("invalid")
                self.entries = []

            def search(self, search_base, search_filter, search_scope, attributes):
                self.entries = [
                    SimpleNamespace(
                        distinguishedName="CN=Joao,OU=Users,DC=example,DC=com",
                        givenName="Joao",
                        sn="Silva",
                        displayName="Joao Silva",
                        mail=mail,
                        sAMAccountName="joao",
                    )
                ]

            def unbind(self):
                return None

        ldap3_module = ModuleType("ldap3")
        ldap3_module.Connection = FakeConnection
        ldap3_module.Server = lambda *args, **kwargs: object()
        ldap3_module.Tls = lambda *args, **kwargs: object()
        ldap3_module.NONE = object()
        ldap3_module.SUBTREE = object()
        ldap3_module.NTLM = object()
        exceptions_module = ModuleType("ldap3.core.exceptions")
        exceptions_module.LDAPBindError = LDAPBindError
        return attempts, ldap3_module, exceptions_module

    def test_login_falha_sem_diretorio_ativo(self):
        LDAPDirectory.objects.update(ativo=False)
        backend = LDAPBackend()
        self.assertIsNone(backend.authenticate(None, username="joao", password="123"))

    def test_login_ldap_cria_usuario_no_primeiro_acesso(self):
        attempts, ldap3_module, exceptions_module = self._fake_ldap_modules(
            {"CN=Joao,OU=Users,DC=example,DC=com"}
        )
        with patch.dict("sys.modules", {"ldap3": ldap3_module, "ldap3.core.exceptions": exceptions_module}):
            user = LDAPBackend().authenticate(None, username="joao", password="123")
        self.assertEqual(user.username, "joao")
        self.assertTrue(UsuarioPerfil.objects.filter(user=user, nome_completo="Joao Silva").exists())
        self.assertIn("cn=svc", attempts)

    def test_login_ldap_fallback_para_upn(self):
        attempts, ldap3_module, exceptions_module = self._fake_ldap_modules({"joao@example.com"})
        with patch.dict("sys.modules", {"ldap3": ldap3_module, "ldap3.core.exceptions": exceptions_module}):
            user = LDAPBackend().authenticate(None, username="joao", password="123")
        self.assertEqual(user.username, "joao")
        self.assertIn("joao@example.com", attempts)

    def test_login_ldap_sem_mail_nao_apaga_email_cadastrado(self):
        user = User.objects.create_user(username="joao", password="123", email="joao@spi.local")
        attempts, ldap3_module, exceptions_module = self._fake_ldap_modules(
            {"CN=Joao,OU=Users,DC=example,DC=com"},
            mail="",
        )

        with patch.dict("sys.modules", {"ldap3": ldap3_module, "ldap3.core.exceptions": exceptions_module}):
            authenticated = LDAPBackend().authenticate(None, username="joao", password="123")

        user.refresh_from_db()
        self.assertEqual(authenticated, user)
        self.assertEqual(user.email, "joao@spi.local")
        self.assertIn("cn=svc", attempts)

    def test_login_ldap_senha_invalida_retorna_none(self):
        attempts, ldap3_module, exceptions_module = self._fake_ldap_modules(set())
        with patch.dict("sys.modules", {"ldap3": ldap3_module, "ldap3.core.exceptions": exceptions_module}):
            user = LDAPBackend().authenticate(None, username="joao", password="errada")
        self.assertIsNone(user)
        self.assertIn("CN=Joao,OU=Users,DC=example,DC=com", attempts)
