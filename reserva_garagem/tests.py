"""Testes do módulo de reserva de garagem."""

from __future__ import annotations

from datetime import timedelta
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acls.models import Recurso, RegraAcesso
from mensageria_assincrona.models import MensagemDestino
from usuarios.models import UsuarioPerfil

from .forms import ReservaGaragemAnaliseForm, ReservaGaragemSolicitacaoForm
from .models import ConfiguracaoReservaGaragem, ReservaGaragem, ReservaGaragemEvento, VagaGaragem
from .services import cancelar_reserva, deferir_reserva, indeferir_reserva


class ReservaGaragemBaseTest(TestCase):
    """Monta usuários, ACL, grupo fiscal e vagas base para os cenários do módulo."""

    def setUp(self):
        user_model = get_user_model()
        self.solicitante = user_model.objects.create_user(username="solicitante", password="123", first_name="Ana")
        self.fiscal = user_model.objects.create_user(username="fiscal", password="123", first_name="Carlos")
        self.admin = user_model.objects.create_user(username="admin-garagem", password="123", first_name="Admin")
        self.outro = user_model.objects.create_user(username="outro", password="123", first_name="Bianca")
        for usuario in [self.solicitante, self.fiscal, self.admin, self.outro]:
            perfil, _created = UsuarioPerfil.objects.get_or_create(user=usuario)
            perfil.nome_completo = usuario.get_full_name() or usuario.username
            perfil.save(update_fields=["nome_completo", "atualizado_em"])

        self.recurso, _ = Recurso.objects.get_or_create(
            slug="reserva_garagem",
            defaults={"nome": "Reserva de Garagem", "url_base": "/reserva-garagem/"},
        )
        regra_modificacao = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_MODIFICACAO,
        )
        regra_modificacao.usuarios.add(self.solicitante, self.outro)
        regra_controle = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL,
        )
        regra_controle.usuarios.add(self.admin)
        regra_leitura = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_LEITURA,
        )
        regra_leitura.usuarios.add(self.fiscal)

        self.grupo_fiscais = Group.objects.create(name="Fiscais Garagem")
        self.fiscal.groups.add(self.grupo_fiscais)
        config = ConfiguracaoReservaGaragem.singleton()
        config.grupo_fiscais = self.grupo_fiscais
        config.save(update_fields=["grupo_fiscais", "atualizado_em"])

        self.vaga_a = VagaGaragem.objects.create(nome="Vaga A", localizacao="Subsolo", cor="#123456")
        self.vaga_b = VagaGaragem.objects.create(nome="Vaga B", localizacao="Térreo", cor="#654321")

    def _data_base(self, days=3):
        return timezone.localdate() + timedelta(days=days)

    def _form_data(self, **overrides):
        data_inicial = overrides.pop("data_inicial", self._data_base())
        data_final = overrides.pop("data_final", data_inicial)
        data = {
            "vaga": overrides.pop("vaga", self.vaga_a.pk),
            "data_inicial": data_inicial.isoformat(),
            "data_final": data_final.isoformat(),
            "recorrencia": overrides.pop("recorrencia", ""),
            "marca_veiculo": overrides.pop("marca_veiculo", "Toyota"),
            "modelo_veiculo": overrides.pop("modelo_veiculo", "Corolla"),
            "cor_veiculo": overrides.pop("cor_veiculo", "Prata"),
            "placa_veiculo": overrides.pop("placa_veiculo", "ABC1D23"),
            "observacoes": overrides.pop("observacoes", "Uso institucional"),
        }
        data.update(overrides)
        return data

    def _reserva(self, **overrides):
        data = overrides.pop("data", self._data_base())
        return ReservaGaragem.objects.create(
            vaga=overrides.pop("vaga", self.vaga_a),
            solicitante=overrides.pop("solicitante", self.solicitante),
            status=overrides.pop("status", ReservaGaragem.Status.AGUARDANDO_APROVACAO),
            data=data,
            responsavel=overrides.pop("responsavel", "Ana"),
            marca_veiculo=overrides.pop("marca_veiculo", "Toyota"),
            modelo_veiculo=overrides.pop("modelo_veiculo", "Corolla"),
            cor_veiculo=overrides.pop("cor_veiculo", "Prata"),
            placa_veiculo=overrides.pop("placa_veiculo", "ABC1D23"),
            observacoes=overrides.pop("observacoes", ""),
            serie_id=overrides.pop("serie_id", None),
            **overrides,
        )


class ReservaGaragemFormTests(ReservaGaragemBaseTest):
    """Valida recorrência, conflitos e decisão fiscal."""

    def test_cria_reserva_valida_sem_horario(self):
        """A solicitação usa somente datas e dados do veículo."""

        form = ReservaGaragemSolicitacaoForm(
            data=self._form_data(),
            request_user=self.solicitante,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_expande_intervalo_continuo(self):
        """O intervalo contínuo deve materializar um dia por ocorrência."""

        inicio = self._data_base()
        fim = inicio + timedelta(days=2)
        form = ReservaGaragemSolicitacaoForm(
            data=self._form_data(data_inicial=inicio, data_final=fim),
            request_user=self.solicitante,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_recurrence_dates(), [inicio, inicio + timedelta(days=1), fim])

    def test_expande_recorrencia_em_dias_uteis(self):
        """A expansão em dias úteis deve ignorar sábado e domingo."""

        inicio = self._data_base()
        while inicio.weekday() != 4:
            inicio += timedelta(days=1)
        fim = inicio + timedelta(days=3)
        form = ReservaGaragemSolicitacaoForm(
            data=self._form_data(data_inicial=inicio, data_final=fim, recorrencia="business_daily"),
            request_user=self.solicitante,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.get_recurrence_dates(), [inicio, inicio + timedelta(days=3)])

    def test_permite_fim_de_semana_em_reserva_normal(self):
        """O módulo aceita sábado e domingo fora da recorrência útil."""

        inicio = self._data_base()
        while inicio.weekday() != 5:
            inicio += timedelta(days=1)
        form = ReservaGaragemSolicitacaoForm(
            data=self._form_data(data_inicial=inicio, data_final=inicio),
            request_user=self.solicitante,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_conflito_de_vaga_so_quando_existir_deferida(self):
        """Pendências coexistem, mas reserva deferida bloqueia a vaga."""

        data = self._data_base()
        self._reserva(data=data, status=ReservaGaragem.Status.DEFERIDA)
        form = ReservaGaragemSolicitacaoForm(
            data=self._form_data(data_inicial=data, data_final=data),
            request_user=self.outro,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("vaga", str(form.errors).lower())

    def test_conflito_de_placa_no_mesmo_dia(self):
        """A mesma placa não pode aparecer duas vezes na mesma data."""

        data = self._data_base()
        self._reserva(data=data, placa_veiculo="ABC1D23", status=ReservaGaragem.Status.AGUARDANDO_APROVACAO)
        form = ReservaGaragemSolicitacaoForm(
            data=self._form_data(data_inicial=data, data_final=data, placa_veiculo="abc1d23"),
            request_user=self.outro,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("placa", str(form.errors).lower())

    def test_conflito_de_solicitante_no_mesmo_dia(self):
        """O mesmo solicitante não pode ter mais de uma reserva por data."""

        data = self._data_base()
        self._reserva(data=data, solicitante=self.solicitante, placa_veiculo="AAA1A11")
        form = ReservaGaragemSolicitacaoForm(
            data=self._form_data(data_inicial=data, data_final=data, placa_veiculo="BBB2B22"),
            request_user=self.solicitante,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("você já possui reserva", str(form.errors).lower())

    def test_analise_exige_justificativa_no_indeferimento(self):
        """A justificativa continua obrigatória na decisão negativa."""

        form = ReservaGaragemAnaliseForm(
            data={
                "decisao": "INDEFERIR",
                "justificativa_indeferimento": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("justificativa", form.errors["justificativa_indeferimento"][0].lower())


class ReservaGaragemServiceTests(ReservaGaragemBaseTest):
    """Valida deferimento, indeferimento, cancelamento e mensageria."""

    @patch("reserva_garagem.services.publicar_mensagem")
    @patch("reserva_garagem.services.criar_mensagem_rascunho")
    def test_deferimento_em_bloco_da_serie(self, criar_mensagem, publicar_mensagem):
        """A análise fiscal positiva deve atingir todas as ocorrências da série."""

        mensagem = type("MensagemFake", (), {"usuarios_alvo": type("Alvo", (), {"add": lambda *args, **kwargs: None})()})()
        criar_mensagem.return_value = mensagem
        serie_id = uuid.uuid4()
        reserva_a = self._reserva(data=self._data_base(), placa_veiculo="AAA1A11", serie_id=serie_id)
        reserva_b = self._reserva(
            data=self._data_base() + timedelta(days=1),
            placa_veiculo="AAA1A11",
            serie_id=serie_id,
        )

        queryset = deferir_reserva(reserva_a, fiscal=self.fiscal)

        self.assertEqual(queryset.count(), 2)
        self.assertEqual(
            ReservaGaragem.objects.filter(serie_id=serie_id, status=ReservaGaragem.Status.DEFERIDA).count(),
            2,
        )
        self.assertEqual(
            ReservaGaragemEvento.objects.filter(acao=ReservaGaragemEvento.Acao.DEFERIMENTO).count(),
            2,
        )
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)
        reserva_b.refresh_from_db()
        self.assertEqual(reserva_b.fiscal_responsavel, self.fiscal)

    @patch("reserva_garagem.services.publicar_mensagem")
    @patch("reserva_garagem.services.criar_mensagem_rascunho")
    def test_indeferimento_em_bloco_da_serie(self, criar_mensagem, publicar_mensagem):
        """O indeferimento deve gravar justificativa nas ocorrências da série."""

        mensagem = type("MensagemFake", (), {"usuarios_alvo": type("Alvo", (), {"add": lambda *args, **kwargs: None})()})()
        criar_mensagem.return_value = mensagem
        serie_id = uuid.uuid4()
        reserva_a = self._reserva(data=self._data_base(), placa_veiculo="CCC3C33", serie_id=serie_id)
        self._reserva(
            data=self._data_base() + timedelta(days=1),
            placa_veiculo="CCC3C33",
            serie_id=serie_id,
        )

        indeferir_reserva(reserva_a, fiscal=self.fiscal, justificativa="Sem vagas operacionais.")

        self.assertEqual(
            ReservaGaragem.objects.filter(
                serie_id=serie_id,
                status=ReservaGaragem.Status.INDEFERIDA,
                justificativa_indeferimento="Sem vagas operacionais.",
            ).count(),
            2,
        )
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)

    def test_cancelamento_apenas_enquanto_pendente(self):
        """O solicitante só cancela uma série antes da análise fiscal."""

        reserva = self._reserva()
        cancelar_reserva(reserva, usuario=self.solicitante)
        reserva.refresh_from_db()

        self.assertEqual(reserva.status, ReservaGaragem.Status.CANCELADA)

    def test_conflito_de_vaga_apenas_no_deferimento(self):
        """Pendências paralelas são permitidas até o momento da decisão fiscal."""

        data = self._data_base()
        primeira = self._reserva(data=data, placa_veiculo="AAA1A11")
        segunda = self._reserva(
            data=data,
            solicitante=self.outro,
            placa_veiculo="BBB2B22",
        )
        deferir_reserva(primeira, fiscal=self.fiscal)

        with self.assertRaisesMessage(Exception, "vaga selecionada"):
            deferir_reserva(segunda, fiscal=self.fiscal)


class ReservaGaragemViewsTests(ReservaGaragemBaseTest):
    """Valida agenda, fila fiscal, CRUD administrativo e dashboard."""

    def test_agenda_exibe_reserva_pendente_em_cinza(self):
        """A agenda precisa renderizar pendências com a cor cinza definida no plano."""

        self._reserva(status=ReservaGaragem.Status.AGUARDANDO_APROVACAO)
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))

        self.assertContains(response, "reservas-data")
        self.assertContains(response, "#9ca3af")

    def test_agenda_omite_indeferidas_e_canceladas(self):
        """Somente pendentes e deferidas ficam visíveis no calendário."""

        self._reserva(status=ReservaGaragem.Status.INDEFERIDA, placa_veiculo="IND1E00")
        self._reserva(status=ReservaGaragem.Status.CANCELADA, placa_veiculo="CAN1C00")
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))

        self.assertNotContains(response, "IND1E00")
        self.assertNotContains(response, "CAN1C00")

    def test_fila_fiscal_restrita_a_fiscais_e_controle_total(self):
        """Usuário comum não deve acessar a fila de deferimento."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:fila_fiscal"))

        self.assertEqual(response.status_code, 403)

    def test_crud_de_vagas_restrito_ao_controle_total(self):
        """O cadastro da garagem fica reservado ao perfil administrativo."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:vaga_list"))
        self.assertEqual(response.status_code, 403)

        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:vaga_list"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_renderiza_ocupacao_media_e_ranking(self):
        """O painel deve expor a taxa média diária e o ranking de vagas."""

        self._reserva(status=ReservaGaragem.Status.DEFERIDA, data=self._data_base(), placa_veiculo="DDD4D44")
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:dashboard"))

        self.assertContains(response, "Taxa média diária de ocupação")
        self.assertContains(response, "Ranking das vagas mais usadas")

    def test_reserva_create_materializa_serie(self):
        """A view de criação deve gerar uma ocorrência por dia do intervalo."""

        self.client.login(username="solicitante", password="123")
        inicio = self._data_base()
        fim = inicio + timedelta(days=2)
        response = self.client.post(
            reverse("reserva_garagem:reserva_create"),
            data=self._form_data(data_inicial=inicio, data_final=fim, placa_veiculo="EEE5E55"),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ReservaGaragem.objects.filter(placa_veiculo="EEE5E55").count(), 3)

    def test_analise_indeferimento_exige_fiscal(self):
        """A tela de análise deve bloquear quem não pertence ao fluxo fiscal."""

        reserva = self._reserva()
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:fila_fiscal_analise", args=[reserva.pk]))

        self.assertEqual(response.status_code, 403)

    @patch("reserva_garagem.services.publicar_mensagem")
    @patch("reserva_garagem.services.criar_mensagem_rascunho")
    def test_analise_view_indeferimento_em_bloco(self, criar_mensagem, publicar_mensagem):
        """A view fiscal deve persistir a decisão na série inteira."""

        mensagem = type("MensagemFake", (), {"usuarios_alvo": type("Alvo", (), {"add": lambda *args, **kwargs: None})()})()
        criar_mensagem.return_value = mensagem
        serie_id = uuid.uuid4()
        reserva = self._reserva(serie_id=serie_id, placa_veiculo="FFF6F66")
        self._reserva(
            data=self._data_base() + timedelta(days=1),
            serie_id=serie_id,
            placa_veiculo="FFF6F66",
        )
        self.client.login(username="fiscal", password="123")
        response = self.client.post(
            reverse("reserva_garagem:fila_fiscal_analise", args=[reserva.pk]),
            data={"decisao": "INDEFERIR", "justificativa_indeferimento": "Teste"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ReservaGaragem.objects.filter(serie_id=serie_id, status=ReservaGaragem.Status.INDEFERIDA).count(),
            2,
        )
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)

