"""Testes do módulo de reserva de espaços."""

from datetime import time
from datetime import timedelta
import uuid

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acls.models import Recurso, RegraAcesso

from .forms import ReservaRecursoForm
from .models import ObjetoReservavel, ReservaRecurso


class ReservaRecursoFormTests(TestCase):
    """Valida regras temporais, recorrência e conflito do formulário."""

    def setUp(self):
        self.objeto = ObjetoReservavel.objects.create(
            nome="Sala 01",
            localizacao="2º andar",
        )

    def test_bloqueia_conflito_de_horario_no_mesmo_objeto(self):
        """Não permite sobreposição de reservas do mesmo recurso."""

        data = timezone.localdate() + timedelta(days=1)
        ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=data,
            hora_inicio=time(10, 0),
            hora_fim=time(11, 0),
            titulo="Reserva existente",
            responsavel="Ana",
        )
        form = ReservaRecursoForm(
            data={
                "objeto": self.objeto.pk,
                "data": data.isoformat(),
                "hora_inicio": "10:30",
                "hora_fim": "11:30",
                "titulo": "Conflito",
                "responsavel": "João",
                "observacoes": "",
                "recorrencia": "",
                "recorrencia_fim": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn(form.conflict_error_message, form.non_field_errors())

    def test_gera_recorrencia_quinzenal(self):
        """A expansão quinzenal deve incluir as datas até o fim informado."""

        data = timezone.localdate() + timedelta(days=1)
        recorrencia_fim = data + timedelta(days=28)
        form = ReservaRecursoForm(
            data={
                "objeto": self.objeto.pk,
                "data": data.isoformat(),
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
        self.assertEqual(datas[1], data + timedelta(days=14))


class ReservaPermissionsTests(TestCase):
    """Garante a integração entre ACL do módulo e autoria da reserva."""

    def setUp(self):
        self.recurso, _ = Recurso.objects.get_or_create(
            slug="reserva_espacos",
            defaults={"nome": "Reserva de Espaços"},
        )
        self.cliente = User.objects.create_user(username="cliente", password="123")
        self.outro = User.objects.create_user(username="outro", password="123")
        self.admin_global = User.objects.create_user(username="admin_global", password="123")
        self.objeto = ObjetoReservavel.objects.create(nome="Carro 01")
        self.reserva = ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=timezone.localdate() + timedelta(days=1),
            hora_inicio=time(10, 0),
            hora_fim=time(11, 0),
            titulo="Visita técnica",
            responsavel="Cliente",
            criado_por=self.cliente,
        )

        regra_cliente = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_MODIFICACAO,
        )
        regra_cliente.usuarios.add(self.cliente, self.outro)
        regra_admin = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL,
        )
        regra_admin.usuarios.add(self.admin_global)

    def test_cliente_nao_pode_editar_reserva_de_terceiro(self):
        """Quem tem modificação como cliente só altera o que criou."""

        self.client.login(username="outro", password="123")
        response = self.client.get(reverse("reserva_espacos:reserva_update", kwargs={"pk": self.reserva.pk}))
        self.assertEqual(response.status_code, 403)

    def test_controle_total_pode_editar_reserva_de_terceiro(self):
        """Quem tem controle total continua administrando qualquer reserva."""

        self.client.login(username="admin_global", password="123")
        response = self.client.get(reverse("reserva_espacos:reserva_update", kwargs={"pk": self.reserva.pk}))
        self.assertEqual(response.status_code, 200)


class AgendaDashboardTests(TestCase):
    """Valida rendering básico da agenda e do dashboard."""

    def setUp(self):
        self.recurso, _ = Recurso.objects.get_or_create(
            slug="reserva_espacos",
            defaults={"nome": "Reserva de Espaços"},
        )
        self.user = User.objects.create_user(username="agenda", password="123")
        regra = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL,
        )
        regra.usuarios.add(self.user)
        self.objeto = ObjetoReservavel.objects.create(nome="Auditório principal")
        ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=timezone.localdate() + timedelta(days=2),
            hora_inicio=time(14, 0),
            hora_fim=time(15, 0),
            titulo="Palestra",
            responsavel="Equipe",
            criado_por=self.user,
        )

    def test_agenda_renderiza_sem_filtro_de_categoria(self):
        """A agenda simplificada precisa expor só o filtro por objeto."""

        self.client.login(username="agenda", password="123")
        response = self.client.get(reverse("reserva_espacos:agenda"))
        self.assertContains(response, "Filtro por objeto")
        self.assertNotContains(response, "Filtro por categoria")
        self.assertContains(response, "reservas-data")

    def test_dashboard_renderiza_ranking(self):
        """O dashboard deve trazer o bloco de ranking de usuários."""

        self.client.login(username="agenda", password="123")
        response = self.client.get(reverse("reserva_espacos:dashboard"))
        self.assertContains(response, "Quem mais reserva")

    def test_dashboard_renderiza_sem_combobox_de_categoria(self):
        """O dashboard simplificado não deve mais exibir combobox de categoria."""
        self.client.login(username="agenda", password="123")
        response = self.client.get(reverse("reserva_espacos:dashboard"))
        self.assertNotContains(response, 'name="categoria"')

    def test_detalhe_renderiza_nomes_clicaveis_para_modal_de_contato(self):
        """O detalhe deve tornar responsável e reservado por clicáveis para contato."""

        self.client.login(username="agenda", password="123")
        reserva = ReservaRecurso.objects.get(titulo="Palestra")
        response = self.client.get(reverse("reserva_espacos:reserva_detail", kwargs={"pk": reserva.pk}))
        self.assertContains(response, 'data-bs-target="#ramalContactModal"', count=2)
        self.assertContains(response, 'aria-label="Abrir contato de agenda"')
        self.assertContains(response, 'id="ramalContactModal"')


class ReservaCreateResponsavelTests(TestCase):
    """Garante que o responsável do cadastro novo seja sempre o próprio usuário."""

    def setUp(self):
        self.recurso, _ = Recurso.objects.get_or_create(
            slug="reserva_espacos",
            defaults={"nome": "Reserva de Espaços"},
        )
        self.user = User.objects.create_user(
            username="responsavel",
            password="123",
            first_name="Maria",
            last_name="Silva",
        )
        regra = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_MODIFICACAO,
        )
        regra.usuarios.add(self.user)
        self.objeto = ObjetoReservavel.objects.create(nome="Sala 99")

    def test_post_ignora_responsavel_informado_e_grava_usuario_logado(self):
        """O backend deve sobrescrever o campo responsável no cadastro inicial."""

        self.client.login(username="responsavel", password="123")
        response = self.client.post(
            reverse("reserva_espacos:reserva_create"),
            data={
                "objeto": self.objeto.pk,
                "data": (timezone.localdate() + timedelta(days=1)).isoformat(),
                "hora_inicio": "09:00",
                "hora_fim": "10:00",
                "titulo": "Reserva automática",
                "responsavel": "Outro nome",
                "observacoes": "",
                "recorrencia": "",
                "recorrencia_fim": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        reserva = ReservaRecurso.objects.get(titulo="Reserva automática")
        self.assertEqual(reserva.responsavel, "Maria Silva")


class ReservaConflitoModalTests(TestCase):
    """Garante a renderização do modal quando existe conflito de agenda."""

    def setUp(self):
        self.recurso, _ = Recurso.objects.get_or_create(
            slug="reserva_espacos",
            defaults={"nome": "Reserva de Espaços"},
        )
        self.user = User.objects.create_user(username="modal", password="123")
        regra = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL,
        )
        regra.usuarios.add(self.user)
        self.objeto = ObjetoReservavel.objects.create(nome="Sala modal")
        self.data_reserva = timezone.localdate() + timedelta(days=2)
        self.reserva = ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=self.data_reserva,
            hora_inicio=time(10, 0),
            hora_fim=time(11, 0),
            titulo="Reserva base",
            responsavel="Equipe",
            criado_por=self.user,
        )

    def test_create_renderiza_modal_de_conflito(self):
        """O cadastro deve devolver o modal quando houver sobreposição."""

        self.client.login(username="modal", password="123")
        response = self.client.post(
            reverse("reserva_espacos:reserva_create"),
            data={
                "objeto": self.objeto.pk,
                "data": self.data_reserva.isoformat(),
                "hora_inicio": "10:30",
                "hora_fim": "11:30",
                "titulo": "Reserva em conflito",
                "responsavel": "Outro nome",
                "observacoes": "",
                "recorrencia": "",
                "recorrencia_fim": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reservaConflitoModal"')
        self.assertContains(response, ReservaRecursoForm.conflict_error_message)
        self.assertNotContains(response, '<ul class="errorlist"><li>Já existe uma reserva para este objeto no intervalo informado.</li></ul>', html=False)

    def test_update_renderiza_modal_de_conflito(self):
        """A edição simples deve devolver o modal quando houver conflito."""

        outra_reserva = ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=self.data_reserva,
            hora_inicio=time(12, 0),
            hora_fim=time(13, 0),
            titulo="Reserva editável",
            responsavel="Equipe",
            criado_por=self.user,
        )
        self.client.login(username="modal", password="123")
        response = self.client.post(
            reverse("reserva_espacos:reserva_update", kwargs={"pk": outra_reserva.pk}),
            data={
                "objeto": self.objeto.pk,
                "data": self.data_reserva.isoformat(),
                "hora_inicio": "10:30",
                "hora_fim": "11:30",
                "titulo": "Reserva editável",
                "responsavel": "Equipe",
                "observacoes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reservaConflitoModal"')
        self.assertContains(response, ReservaRecursoForm.conflict_error_message)

    def test_series_update_all_renderiza_modal_de_conflito(self):
        """A edição da série inteira deve devolver o modal quando houver conflito."""

        ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=self.data_reserva + timedelta(days=7),
            hora_inicio=time(10, 0),
            hora_fim=time(11, 0),
            titulo="Conflito da série",
            responsavel="Equipe",
            criado_por=self.user,
        )
        serie_id = uuid.uuid4()
        ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=self.data_reserva + timedelta(days=7),
            hora_inicio=time(12, 0),
            hora_fim=time(13, 0),
            titulo="Reserva recorrente 1",
            responsavel="Equipe",
            criado_por=self.user,
            serie_id=serie_id,
        )
        ReservaRecurso.objects.create(
            objeto=self.objeto,
            data=self.data_reserva + timedelta(days=14),
            hora_inicio=time(12, 0),
            hora_fim=time(13, 0),
            titulo="Reserva recorrente 2",
            responsavel="Equipe",
            criado_por=self.user,
            serie_id=serie_id,
        )
        primeira_ocorrencia = ReservaRecurso.objects.filter(serie_id=serie_id).order_by("data").first()

        self.client.login(username="modal", password="123")
        response = self.client.post(
            reverse("reserva_espacos:reserva_update", kwargs={"pk": primeira_ocorrencia.pk}),
            data={
                "objeto": self.objeto.pk,
                "data": primeira_ocorrencia.data.isoformat(),
                "hora_inicio": "10:30",
                "hora_fim": "11:30",
                "titulo": "Reserva recorrente 1",
                "responsavel": "Equipe",
                "observacoes": "",
                "apply_scope": "all",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="reservaConflitoModal"')
        self.assertContains(response, ReservaRecursoForm.conflict_error_message)
