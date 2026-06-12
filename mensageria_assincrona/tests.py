# Criado por OpenAI Codex em 12/06/2026
# Exercita regras críticas de publicação, pendências, permissões e integração básica da UI.

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acls.models import Recurso, RegraAcesso
from setores.models import SetorNode, UserSetorMembership
from usuarios.models import UsuarioPerfil

from .models import Mensagem, MensagemDestino
from .services import (
    agendar_mensagem,
    cancelar_mensagem,
    criar_mensagem_rascunho,
    listar_pendentes_usuario,
    marcar_ciente,
    marcar_visualizacao,
    publicar_mensagem,
)


class MensageriaBaseTest(TestCase):
    """Monta usuários, ACL e setor compartilhados pelos cenários do módulo."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin-mensageria", password="123", first_name="Admin")
        self.destinatario = User.objects.create_user(username="ana", password="123", first_name="Ana")
        self.destinatario_2 = User.objects.create_user(username="bruno", password="123", first_name="Bruno")
        self.sem_acl = User.objects.create_user(username="clara", password="123", first_name="Clara")
        self.inativo = User.objects.create_user(username="desligado", password="123", is_active=False)

        for user in [self.admin, self.destinatario, self.destinatario_2, self.sem_acl]:
            perfil, _created = UsuarioPerfil.objects.get_or_create(user=user)
            perfil.nome_completo = user.get_full_name() or user.username
            perfil.save(update_fields=["nome_completo", "atualizado_em"])

        self.grupo_setor = Group.objects.create(name="Gabinete")
        self.setor = SetorNode.objects.create(group=self.grupo_setor, ativo=True)
        UserSetorMembership.objects.create(user=self.destinatario_2, setor=self.setor)
        UserSetorMembership.objects.create(user=self.inativo, setor=self.setor)

        self.recurso, _ = Recurso.objects.get_or_create(
            slug="mensageria_assincrona",
            defaults={"nome": "Mensageria", "url_base": "/mensageria/"},
        )
        regra = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL)
        regra.usuarios.add(self.admin)


class MensageriaServiceTests(MensageriaBaseTest):
    """Valida publicação, expiração, ciência e command de agendamento."""

    def test_cria_rascunho_sem_destinos(self):
        mensagem = criar_mensagem_rascunho(assunto="Aviso", corpo="Conteúdo", criada_por=self.admin)

        self.assertEqual(mensagem.status_envio, Mensagem.StatusEnvio.RASCUNHO)
        self.assertFalse(mensagem.destinos.exists())

    def test_publicacao_consolida_usuarios_diretos_e_setores_sem_duplicidade(self):
        mensagem = criar_mensagem_rascunho(assunto="Fechamento", corpo="Portal será atualizado", criada_por=self.admin)
        mensagem.usuarios_alvo.add(self.destinatario, self.destinatario_2)
        mensagem.setores_alvo.add(self.setor)

        publicar_mensagem(mensagem, usuario=self.admin)
        mensagem.refresh_from_db()
        destinos = list(mensagem.destinos.order_by("usuario__username"))

        self.assertEqual(mensagem.status_envio, Mensagem.StatusEnvio.PUBLICADA)
        self.assertEqual(len(destinos), 2)
        self.assertEqual(destinos[0].assunto_snapshot, "Fechamento")
        self.assertFalse(mensagem.destinos.filter(usuario=self.inativo).exists())

    def test_expiracao_remove_da_fila_ativa_mas_preserva_historico(self):
        mensagem = criar_mensagem_rascunho(
            assunto="Prazo curto",
            corpo="Mensagem temporária",
            criada_por=self.admin,
            expira_em=timezone.now() - timezone.timedelta(minutes=1),
        )
        mensagem.usuarios_alvo.add(self.destinatario)
        publicar_mensagem(mensagem, usuario=self.admin)

        self.assertEqual(listar_pendentes_usuario(self.destinatario).count(), 0)
        self.assertEqual(MensagemDestino.objects.filter(usuario=self.destinatario).count(), 1)

    def test_visualizacao_nao_equivale_a_ciencia(self):
        mensagem = criar_mensagem_rascunho(assunto="Leia", corpo="Texto", criada_por=self.admin)
        mensagem.usuarios_alvo.add(self.destinatario)
        publicar_mensagem(mensagem, usuario=self.admin)
        destino = mensagem.destinos.get(usuario=self.destinatario)

        marcar_visualizacao(destino, self.destinatario)
        destino.refresh_from_db()
        self.assertIsNotNone(destino.visualizada_em)
        self.assertEqual(destino.status_destinatario, MensagemDestino.StatusDestinatario.PENDENTE)
        self.assertIsNone(destino.ciente_em)

        marcar_ciente(destino, self.destinatario)
        destino.refresh_from_db()
        self.assertEqual(destino.status_destinatario, MensagemDestino.StatusDestinatario.CIENTE)
        self.assertIsNotNone(destino.ciente_em)

    def test_cancelamento_impede_publicacao_posterior(self):
        mensagem = criar_mensagem_rascunho(assunto="Cancelar", corpo="Teste", criada_por=self.admin)
        cancelar_mensagem(mensagem, usuario=self.admin)

        with self.assertRaises(ValueError):
            publicar_mensagem(mensagem, usuario=self.admin)

    def test_command_publica_agendada_uma_unica_vez(self):
        mensagem = criar_mensagem_rascunho(assunto="Agendada", corpo="Disparo", criada_por=self.admin)
        mensagem.usuarios_alvo.add(self.destinatario)
        agendar_mensagem(mensagem, timezone.now() - timezone.timedelta(minutes=2), usuario=self.admin)

        output = StringIO()
        call_command("publicar_mensagens_agendadas", stdout=output)
        call_command("publicar_mensagens_agendadas", stdout=output)

        mensagem.refresh_from_db()
        self.assertEqual(mensagem.status_envio, Mensagem.StatusEnvio.PUBLICADA)
        self.assertEqual(mensagem.destinos.filter(usuario=self.destinatario).count(), 1)


class MensageriaViewTests(MensageriaBaseTest):
    """Cobre acesso à inbox, proteção do admin e componentes globais da UI."""

    def _criar_mensagem_para(self, usuario, assunto="Mensagem", corpo="Conteúdo"):
        mensagem = criar_mensagem_rascunho(assunto=assunto, corpo=corpo, criada_por=self.admin)
        mensagem.usuarios_alvo.add(usuario)
        publicar_mensagem(mensagem, usuario=self.admin)
        return mensagem

    def test_usuario_autenticado_sem_acl_acessa_inbox(self):
        self._criar_mensagem_para(self.sem_acl)
        self.client.login(username="clara", password="123")

        response = self.client.get(reverse("mensageria:minhas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Minhas mensagens")

    def test_usuario_sem_acl_nao_acessa_area_admin(self):
        self.client.login(username="clara", password="123")

        response = self.client.get(reverse("mensageria:admin_list"))

        self.assertEqual(response.status_code, 403)

    def test_usuario_com_controle_total_acessa_area_admin(self):
        self.client.login(username="admin-mensageria", password="123")

        response = self.client.get(reverse("mensageria:admin_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gerencie comunicados internos")

    def test_usuario_nao_confirma_ciencia_de_mensagem_alheia(self):
        mensagem = self._criar_mensagem_para(self.destinatario)
        destino = mensagem.destinos.get(usuario=self.destinatario)
        self.client.login(username="clara", password="123")

        response = self.client.post(reverse("mensageria:ciente"), {"destino_id": destino.pk})

        self.assertEqual(response.status_code, 404)
        destino.refresh_from_db()
        self.assertEqual(destino.status_destinatario, MensagemDestino.StatusDestinatario.PENDENTE)

    def test_topbar_exibe_badge_e_modal_individual(self):
        self._criar_mensagem_para(self.destinatario, assunto="Atualização", corpo="Leia com atenção")
        self.client.login(username="ana", password="123")

        response = self.client.get(reverse("noticias:public_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mensagens")
        self.assertContains(response, "Atualização")
        self.assertContains(response, 'mensageriaPendenciaModal', html=False)

    def test_modal_consolidado_aparece_com_mais_de_tres_pendencias(self):
        for indice in range(4):
            self._criar_mensagem_para(self.destinatario, assunto=f"Msg {indice}", corpo="Pendência")
        self.client.login(username="ana", password="123")

        response = self.client.get(reverse("noticias:public_list"))

        self.assertContains(response, "mensagens pendentes de ciência")
        self.assertContains(response, "Ir para minha caixa de entrada")

    def test_inbox_lista_nao_lidas_no_topo_e_marca_ciente_ao_abrir(self):
        mensagem_antiga = self._criar_mensagem_para(self.destinatario, assunto="Mensagem antiga", corpo="Primeira")
        destino_antigo = mensagem_antiga.destinos.get(usuario=self.destinatario)
        destino_antigo.entregue_em = timezone.now() - timezone.timedelta(days=1)
        destino_antigo.save(update_fields=["entregue_em", "updated_at"])
        marcar_ciente(destino_antigo, self.destinatario)

        mensagem_nova = self._criar_mensagem_para(self.destinatario, assunto="Mensagem nova", corpo="Segunda")
        destino_novo = mensagem_nova.destinos.get(usuario=self.destinatario)
        self.client.login(username="ana", password="123")

        response = self.client.get(reverse("mensageria:minhas"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mensagem antiga")
        self.assertContains(response, "Mensagem nova")
        content = response.content.decode("utf-8")
        self.assertLess(content.index("Mensagem nova"), content.index("Mensagem antiga"))

        detail_response = self.client.get(reverse("mensageria:minha_detail", args=[destino_novo.pk]))
        destino_novo.refresh_from_db()

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(destino_novo.status_destinatario, MensagemDestino.StatusDestinatario.CIENTE)
        self.assertIsNotNone(destino_novo.visualizada_em)
        self.assertIsNotNone(destino_novo.ciente_em)
