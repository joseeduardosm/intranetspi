"""Testes do módulo de reserva de espaços."""

from __future__ import annotations

from datetime import time, timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acls.models import Recurso, RegraAcesso

from .forms import ReservaRecursoForm
from .models import ConfiguracaoReservaEspacos, ObjetoReservavel, ReservaRecurso
from .services import cancelar_reserva_com_escopo, deferir_reserva, indeferir_reserva


class ReservaEspacosBaseTestCase(TestCase):
    """Monta ACL, grupo fiscal e usuários para os cenários do módulo."""

    def setUp(self):
        self.recurso, _ = Recurso.objects.get_or_create(
            slug="reserva_espacos",
            defaults={"nome": "Reserva de Espaços"},
        )
        self.solicitante = User.objects.create_user(username="solicitante", password="123", first_name="Ana")
        self.outro = User.objects.create_user(username="outro", password="123", first_name="Bruno")
        self.fiscal = User.objects.create_user(username="fiscal", password="123", first_name="Carlos")
        self.admin = User.objects.create_user(username="admin", password="123", is_staff=True)
        self.grupo_fiscais = Group.objects.create(name="Fiscais Salas")
        self.fiscal.groups.add(self.grupo_fiscais)
        ConfiguracaoReservaEspacos.singleton().grupo_fiscais = self.grupo_fiscais
        ConfiguracaoReservaEspacos.singleton().save()

        regra_cliente = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_MODIFICACAO,
        )
        regra_cliente.usuarios.add(self.solicitante, self.outro, self.fiscal, self.admin)

        regra_total = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL,
        )
        regra_total.usuarios.add(self.admin)

        self.objeto = ObjetoReservavel.objects.create(nome="Sala 01", localizacao="2º andar")
        self.data_base = timezone.localdate() + timedelta(days=2)

    def _reserva(self, **kwargs):
        dados = {
            "objeto": self.objeto,
            "data": self.data_base,
            "hora_inicio": time(10, 0),
            "hora_fim": time(11, 0),
            "titulo": "Reunião",
            "responsavel": "Ana",
            "observacoes": "",
            "criado_por": self.solicitante,
            "status": ReservaRecurso.Status.AGUARDANDO_APROVACAO,
        }
        dados.update(kwargs)
        return ReservaRecurso.objects.create(**dados)


class ReservaRecursoFormTests(ReservaEspacosBaseTestCase):
    """Valida regras temporais, recorrência e conflitos deferidos."""

    def test_gera_recorrencia_quinzenal(self):
        """A expansão quinzenal deve incluir as datas até o fim informado."""

        recorrencia_fim = self.data_base + timedelta(days=28)
        form = ReservaRecursoForm(
            data={
                "objeto": self.objeto.pk,
                "data": self.data_base.isoformat(),
                "hora_inicio": "10:00",
                "hora_fim": "11:00",
                "titulo": "Quinzenal",
                "responsavel": "João",
                "observacoes": "",
                "recorrencia": "biweekly",
                "recorrencia_fim": recorrencia_fim.isoformat(),
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        datas = form.get_recurrence_dates()
        self.assertEqual(len(datas), 3)
        self.assertEqual(datas[1], self.data_base + timedelta(days=14))

    def test_pendente_conflitante_nao_bloqueia_nova_solicitacao(self):
        """Solicitações pendentes podem coexistir até a análise fiscal."""

        self._reserva()
        form = ReservaRecursoForm(
            data={
                "objeto": self.objeto.pk,
                "data": self.data_base.isoformat(),
                "hora_inicio": "10:30",
                "hora_fim": "11:30",
                "titulo": "Conflito pendente",
                "responsavel": "João",
                "observacoes": "",
                "recorrencia": "",
                "recorrencia_fim": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_deferida_conflitante_bloqueia_formulario(self):
        """Reserva deferida continua ocupando o horário e bloqueando a criação."""

        self._reserva(status=ReservaRecurso.Status.DEFERIDA)
        form = ReservaRecursoForm(
            data={
                "objeto": self.objeto.pk,
                "data": self.data_base.isoformat(),
                "hora_inicio": "10:30",
                "hora_fim": "11:30",
                "titulo": "Conflito deferido",
                "responsavel": "João",
                "observacoes": "",
                "recorrencia": "",
                "recorrencia_fim": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn(form.conflict_error_message, form.non_field_errors())


class ReservaWorkflowTests(ReservaEspacosBaseTestCase):
    """Valida deferimento, indeferimento, cancelamento e mensageria."""

    @patch("reserva_espacos.services.publicar_mensagem")
    @patch("reserva_espacos.services.criar_mensagem_rascunho")
    def test_criacao_recorrrente_notifica_fiscais(self, criar_mensagem, publicar_mensagem):
        """Série criada pelo usuário nasce pendente e avisa o grupo fiscal."""

        self.client.login(username="solicitante", password="123")
        response = self.client.post(
            reverse("reserva_espacos:reserva_create"),
            data={
                "objeto": self.objeto.pk,
                "data": self.data_base.isoformat(),
                "hora_inicio": "09:00",
                "hora_fim": "10:00",
                "titulo": "Série fiscal",
                "responsavel": "Outro nome",
                "observacoes": "",
                "recorrencia": "weekly",
                "recorrencia_fim": (self.data_base + timedelta(days=14)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 302)
        reservas = ReservaRecurso.objects.filter(titulo="Série fiscal").order_by("data")
        self.assertEqual(reservas.count(), 3)
        self.assertTrue(all(item.status == ReservaRecurso.Status.AGUARDANDO_APROVACAO for item in reservas))
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)

    @patch("reserva_espacos.services.publicar_mensagem")
    @patch("reserva_espacos.services.criar_mensagem_rascunho")
    def test_deferimento_em_bloco_da_serie(self, criar_mensagem, publicar_mensagem):
        """A análise fiscal positiva deve atingir todas as ocorrências da série."""

        serie_id = uuid.uuid4()
        reserva_a = self._reserva(serie_id=serie_id)
        reserva_b = self._reserva(
            serie_id=serie_id,
            data=self.data_base + timedelta(days=7),
            titulo="Reunião 2",
        )
        queryset = deferir_reserva(reserva_a, fiscal=self.fiscal)
        self.assertEqual(queryset.count(), 2)
        reserva_a.refresh_from_db()
        reserva_b.refresh_from_db()
        self.assertEqual(reserva_a.status, ReservaRecurso.Status.DEFERIDA)
        self.assertEqual(reserva_b.status, ReservaRecurso.Status.DEFERIDA)
        self.assertEqual(reserva_b.fiscal_responsavel, self.fiscal)
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)

    def test_deferimento_bloqueia_quando_ja_existe_deferida_conflitante(self):
        """Somente uma reserva deferida pode ocupar o mesmo objeto e horário."""

        existente = self._reserva(status=ReservaRecurso.Status.DEFERIDA, titulo="Existente")
        pendente = self._reserva(titulo="Pendente")
        with self.assertRaisesMessage(Exception, "horário conflitante"):
            deferir_reserva(pendente, fiscal=self.fiscal)
        existente.refresh_from_db()
        self.assertEqual(existente.status, ReservaRecurso.Status.DEFERIDA)

    @patch("reserva_espacos.services.publicar_mensagem")
    @patch("reserva_espacos.services.criar_mensagem_rascunho")
    def test_indeferimento_exige_justificativa_e_notifica(self, criar_mensagem, publicar_mensagem):
        """O indeferimento grava a justificativa e notifica o solicitante."""

        reserva = self._reserva()
        indeferir_reserva(reserva, fiscal=self.fiscal, justificativa="Conflito operacional.")
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, ReservaRecurso.Status.INDEFERIDA)
        self.assertEqual(reserva.justificativa_indeferimento, "Conflito operacional.")
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)

    @patch("reserva_espacos.services.publicar_mensagem")
    @patch("reserva_espacos.services.criar_mensagem_rascunho")
    def test_cancelamento_por_periodo_da_serie(self, criar_mensagem, publicar_mensagem):
        """O cancelamento por período atinge só o recorte solicitado da série."""

        serie_id = uuid.uuid4()
        reserva_a = self._reserva(serie_id=serie_id, status=ReservaRecurso.Status.DEFERIDA)
        reserva_b = self._reserva(
            serie_id=serie_id,
            status=ReservaRecurso.Status.DEFERIDA,
            data=self.data_base + timedelta(days=7),
            titulo="Reunião 2",
        )
        reserva_c = self._reserva(
            serie_id=serie_id,
            status=ReservaRecurso.Status.DEFERIDA,
            data=self.data_base + timedelta(days=14),
            titulo="Reunião 3",
        )
        cancelar_reserva_com_escopo(
            reserva_a,
            usuario=self.fiscal,
            apply_scope="range",
            data_inicial=self.data_base,
            data_final=self.data_base + timedelta(days=7),
            motivo_cancelamento="Ajuste de agenda",
        )
        reserva_a.refresh_from_db()
        reserva_b.refresh_from_db()
        reserva_c.refresh_from_db()
        self.assertEqual(reserva_a.status, ReservaRecurso.Status.CANCELADA)
        self.assertEqual(reserva_b.status, ReservaRecurso.Status.CANCELADA)
        self.assertEqual(reserva_c.status, ReservaRecurso.Status.DEFERIDA)
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)


class ReservaViewsTests(ReservaEspacosBaseTestCase):
    """Valida agenda, fila fiscal, permissões e histórico."""

    def test_agenda_renderiza_com_botoes_por_perfil(self):
        """A agenda precisa mostrar o botão pessoal e esconder a área fiscal do cliente."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_espacos:agenda"))
        self.assertContains(response, "Minhas reservas")
        self.assertNotContains(response, "Fila fiscal")

    def test_agenda_mantem_reserva_pendente_serializada(self):
        """A agenda deve expor reservas pendentes para o calendário multi-view."""

        self._reserva()
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_espacos:agenda"))
        self.assertContains(response, "Aguardando aprovação")
        self.assertContains(response, "reservas-data")

    def test_fila_fiscal_restrita_ao_grupo(self):
        """Usuário comum não acessa a fila fiscal."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_espacos:fila_fiscal"))
        self.assertEqual(response.status_code, 403)

        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_espacos:fila_fiscal"))
        self.assertEqual(response.status_code, 200)

    def test_analise_bloqueia_redecisao(self):
        """Uma solicitação já decidida deve abrir em modo somente leitura."""

        reserva = self._reserva(status=ReservaRecurso.Status.DEFERIDA, fiscal_responsavel=self.fiscal)
        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_espacos:fila_fiscal_analise", kwargs={"pk": reserva.pk}))
        self.assertContains(response, "não aceita novo deferimento ou indeferimento")

    def test_minhas_reservas_lista_apenas_reservas_do_usuario(self):
        """A tela pessoal mostra somente as reservas do usuário logado."""

        self._reserva(titulo="Minha")
        self._reserva(titulo="Outra", criado_por=self.outro, responsavel="Bruno")
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_espacos:minhas_reservas"))
        self.assertContains(response, "Minha")
        self.assertNotContains(response, "Outra")

    def test_pre_reserva_fiscal_nasce_deferida(self):
        """A pré-reserva administrativa já nasce ocupando o horário."""

        self.client.login(username="fiscal", password="123")
        response = self.client.post(
            reverse("reserva_espacos:reserva_predefinida_create"),
            data={
                "objeto": self.objeto.pk,
                "data": self.data_base.isoformat(),
                "hora_inicio": "15:00",
                "hora_fim": "16:00",
                "titulo": "Bloqueio fiscal",
                "responsavel": "Carlos",
                "observacoes": "",
                "recorrencia": "",
                "recorrencia_fim": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        reserva = ReservaRecurso.objects.get(titulo="Bloqueio fiscal")
        self.assertEqual(reserva.status, ReservaRecurso.Status.DEFERIDA)
        self.assertEqual(reserva.fiscal_responsavel, self.fiscal)

    def test_detalhe_renderiza_historico_fiscal(self):
        """O detalhe deve exibir a trilha de histórico com origem e escopo."""

        reserva = self._reserva()
        deferir_reserva(reserva, fiscal=self.fiscal)
        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_espacos:reserva_detail", kwargs={"pk": reserva.pk}))
        self.assertContains(response, "Histórico da reserva")
        self.assertContains(response, "Fluxo fiscal")
