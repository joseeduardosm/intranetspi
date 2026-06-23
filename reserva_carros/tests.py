# Criado por OpenAI Codex em 12/06/2026
# Exercita as regras temporais, a análise fiscal, permissões e a integração com a mensageria.

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acls.models import Recurso, RegraAcesso
from mensageria_assincrona.models import MensagemDestino
from usuarios.models import UsuarioPerfil

from .forms import ReservaCarroAnaliseForm, ReservaCarroSolicitacaoForm
from .models import Carro, ConfiguracaoReservaCarros, Motorista, ReservaCarro
from .services import deferir_reserva, indeferir_reserva


class ReservaCarrosBaseTest(TestCase):
    """Monta usuários, ACL, grupo fiscal e cadastros base para os cenários do módulo."""

    def setUp(self):
        User = get_user_model()
        self.solicitante = User.objects.create_user(username="solicitante", password="123", first_name="Ana")
        self.fiscal = User.objects.create_user(username="fiscal", password="123", first_name="Carlos")
        self.admin = User.objects.create_user(username="admin-carros", password="123", first_name="Admin")
        self.outro = User.objects.create_user(username="outro", password="123", first_name="Bianca")
        for user in [self.solicitante, self.fiscal, self.admin, self.outro]:
            perfil, _created = UsuarioPerfil.objects.get_or_create(user=user)
            perfil.nome_completo = user.get_full_name() or user.username
            perfil.save(update_fields=["nome_completo", "atualizado_em"])

        self.recurso, _ = Recurso.objects.get_or_create(
            slug="reserva_carros",
            defaults={"nome": "Reserva de Carros", "url_base": "/reserva-carros/"},
        )
        regra_leitura = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_LEITURA)
        regra_leitura.usuarios.add(self.solicitante, self.outro)
        regra_admin = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL)
        regra_admin.usuarios.add(self.admin)

        self.grupo_fiscais = Group.objects.create(name="Fiscais Carros")
        self.fiscal.groups.add(self.grupo_fiscais)
        config = ConfiguracaoReservaCarros.singleton()
        config.grupo_fiscais = self.grupo_fiscais
        config.save(update_fields=["grupo_fiscais", "atualizado_em"])

        self.carro = Carro.objects.create(marca="Toyota", modelo="Corolla", placa="ABC1D23")
        self.motorista = Motorista.objects.create(nome_completo="Motorista Oficial")

    def _saida_base(self, days=3, hour=9):
        agora = timezone.localtime(timezone.now())
        base = (agora + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
        while base.weekday() >= 5:
            base += timedelta(days=1)
        return base

    def _reserva(self, **overrides):
        saida = overrides.pop("saida_planejada_em", self._saida_base())
        retorno = overrides.pop("retorno_planejado_em", saida + timedelta(hours=8))
        reserva = ReservaCarro.objects.create(
            solicitante=overrides.pop("solicitante", self.solicitante),
            saida_planejada_em=saida,
            retorno_planejado_em=retorno,
            destino_endereco=overrides.pop("destino_endereco", "Avenida Paulista, 1000, São Paulo/SP"),
            modo_destino=overrides.pop("modo_destino", ReservaCarro.ModoDestino.AGUARDAR_NO_LOCAL),
            motivo_viagem=overrides.pop("motivo_viagem", "Reunião institucional"),
            observacoes_solicitante=overrides.pop("observacoes_solicitante", ""),
            local_saida=ReservaCarro.local_saida_padrao,
            **overrides,
        )
        return reserva


class ReservaCarrosFormTests(ReservaCarrosBaseTest):
    """Valida as regras temporais do cadastro inicial e da decisão fiscal."""

    def _base_form_data(self, saida, retorno):
        return {
            "saida_planejada_em": saida.strftime("%Y-%m-%dT%H:%M"),
            "retorno_planejado_em": retorno.strftime("%Y-%m-%dT%H:%M"),
            "destino_endereco": "Rua Teste, 10",
            "modo_destino": ReservaCarro.ModoDestino.AGUARDAR_NO_LOCAL,
            "motivo_viagem": "Visita técnica",
            "observacoes_solicitante": "",
            "passageiros": [self.outro.pk],
        }

    def test_cria_solicitacao_valida(self):
        saida = self._saida_base()
        retorno = saida + timedelta(hours=6)
        form = ReservaCarroSolicitacaoForm(data=self._base_form_data(saida, retorno), request_user=self.solicitante)

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_exibe_nome_completo_no_seletor_de_passageiros(self):
        self.outro.first_name = "Bianca"
        self.outro.last_name = "Souza"
        self.outro.save(update_fields=["first_name", "last_name"])

        form = ReservaCarroSolicitacaoForm(request_user=self.solicitante)

        self.assertEqual(form.fields["passageiros"].label_from_instance(self.outro), "Bianca Souza")

    def test_bloqueia_saida_com_menos_de_dois_dias(self):
        # Mantém o cenário sempre abaixo do mínimo de 2 dias, sem depender do dia da semana atual.
        agora = timezone.localtime(timezone.now()) + timedelta(hours=12)
        form = ReservaCarroSolicitacaoForm(
            data=self._base_form_data(agora, agora + timedelta(hours=3)),
            request_user=self.solicitante,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("2 dias de antecedência", form.errors["saida_planejada_em"][0])

    def test_bloqueia_saida_alem_de_trinta_dias(self):
        saida = self._saida_base(days=31)
        retorno = saida + timedelta(hours=3)
        form = ReservaCarroSolicitacaoForm(data=self._base_form_data(saida, retorno), request_user=self.solicitante)

        self.assertFalse(form.is_valid())
        self.assertIn("30 dias", form.errors["saida_planejada_em"][0])

    def test_bloqueia_saida_iniciando_no_fim_de_semana(self):
        saida = self._saida_base()
        while saida.weekday() != 5:
            saida += timedelta(days=1)
        retorno = saida + timedelta(hours=4)
        form = ReservaCarroSolicitacaoForm(data=self._base_form_data(saida, retorno), request_user=self.solicitante)

        self.assertFalse(form.is_valid())
        self.assertIn("fim de semana", form.errors["saida_planejada_em"][0])

    def test_permita_viagem_de_sexta_para_sabado(self):
        saida = self._saida_base()
        while saida.weekday() != 4:
            saida += timedelta(days=1)
        retorno = saida + timedelta(days=1, hours=2)
        form = ReservaCarroSolicitacaoForm(data=self._base_form_data(saida, retorno), request_user=self.solicitante)

        self.assertTrue(form.is_valid(), form.errors)

    def test_analise_exige_justificativa_no_indeferimento(self):
        form = ReservaCarroAnaliseForm(
            data={
                "decisao": "INDEFERIR",
                "justificativa_indeferimento": "",
                "deslocamento_ida_minutos": "",
                "deslocamento_retorno_minutos": "",
                "carro": "",
                "motorista": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("justificativa", form.errors["justificativa_indeferimento"][0].lower())


class ReservaCarrosServiceTests(ReservaCarrosBaseTest):
    """Valida deferimento, conflitos, cancelamento e mensageria."""

    def test_calcula_janela_operacional_no_deferimento(self):
        reserva = self._reserva()

        deferir_reserva(
            reserva,
            fiscal=self.fiscal,
            carro=self.carro,
            motorista=self.motorista,
            deslocamento_ida_minutos=30,
            deslocamento_retorno_minutos=45,
        )
        reserva.refresh_from_db()

        self.assertEqual(reserva.status, ReservaCarro.Status.DEFERIDA)
        self.assertEqual(reserva.inicio_bloqueio_em, reserva.saida_planejada_em - timedelta(minutes=30))
        self.assertEqual(reserva.fim_bloqueio_em, reserva.retorno_planejado_em + timedelta(minutes=45))

    def test_permite_sobreposicao_quando_aguardando_aprovacao(self):
        saida = self._saida_base()
        self._reserva(saida_planejada_em=saida, retorno_planejado_em=saida + timedelta(hours=4))
        outra = self._reserva(
            solicitante=self.outro,
            saida_planejada_em=saida + timedelta(minutes=30),
            retorno_planejado_em=saida + timedelta(hours=5),
        )

        self.assertEqual(ReservaCarro.objects.filter(status=ReservaCarro.Status.AGUARDANDO_APROVACAO).count(), 2)
        self.assertEqual(outra.status, ReservaCarro.Status.AGUARDANDO_APROVACAO)

    def test_bloqueia_conflito_de_carro_no_deferimento(self):
        saida = self._saida_base()
        reserva_1 = self._reserva(saida_planejada_em=saida, retorno_planejado_em=saida + timedelta(hours=4))
        deferir_reserva(
            reserva_1,
            fiscal=self.fiscal,
            carro=self.carro,
            motorista=self.motorista,
            deslocamento_ida_minutos=20,
            deslocamento_retorno_minutos=20,
        )
        reserva_2 = self._reserva(
            solicitante=self.outro,
            saida_planejada_em=saida + timedelta(hours=3),
            retorno_planejado_em=saida + timedelta(hours=7),
        )

        with self.assertRaisesMessage(Exception, "carro selecionado"):
            deferir_reserva(
                reserva_2,
                fiscal=self.fiscal,
                carro=self.carro,
                motorista=Motorista.objects.create(nome_completo="Outro motorista"),
                deslocamento_ida_minutos=15,
                deslocamento_retorno_minutos=15,
            )

    def test_bloqueia_conflito_de_motorista_no_deferimento(self):
        saida = self._saida_base()
        reserva_1 = self._reserva(saida_planejada_em=saida, retorno_planejado_em=saida + timedelta(hours=4))
        deferir_reserva(
            reserva_1,
            fiscal=self.fiscal,
            carro=self.carro,
            motorista=self.motorista,
            deslocamento_ida_minutos=20,
            deslocamento_retorno_minutos=20,
        )
        reserva_2 = self._reserva(
            solicitante=self.outro,
            saida_planejada_em=saida + timedelta(hours=3),
            retorno_planejado_em=saida + timedelta(hours=7),
        )
        outro_carro = Carro.objects.create(marca="Honda", modelo="Civic", placa="EFG4H56")

        with self.assertRaisesMessage(Exception, "motorista selecionado"):
            deferir_reserva(
                reserva_2,
                fiscal=self.fiscal,
                carro=outro_carro,
                motorista=self.motorista,
                deslocamento_ida_minutos=15,
                deslocamento_retorno_minutos=15,
            )

    def test_cancelamento_so_antes_da_analise(self):
        reserva = self._reserva()
        self.client.login(username="solicitante", password="123")

        response = self.client.post(reverse("reserva_carros:solicitacao_cancel", args=[reserva.pk]))
        reserva.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(reserva.status, ReservaCarro.Status.CANCELADA)

    def test_deferimento_gera_mensagem_assincrona(self):
        reserva = self._reserva()

        deferir_reserva(
            reserva,
            fiscal=self.fiscal,
            carro=self.carro,
            motorista=self.motorista,
            deslocamento_ida_minutos=30,
            deslocamento_retorno_minutos=30,
        )

        self.assertTrue(MensagemDestino.objects.filter(usuario=self.solicitante).exists())

    def test_indeferimento_gera_mensagem_com_justificativa(self):
        reserva = self._reserva()

        indeferir_reserva(reserva, fiscal=self.fiscal, justificativa="Veículo indisponível")

        destino = MensagemDestino.objects.filter(usuario=self.solicitante).latest("id")
        self.assertIn("Veículo indisponível", destino.corpo_snapshot)


class ReservaCarrosViewTests(ReservaCarrosBaseTest):
    """Cobre acesso às telas principais e o fluxo básico do fiscal."""

    def test_criacao_dispara_mensagem_para_grupo_fiscal(self):
        """A abertura da solicitação precisa alimentar a fila fiscal via mensageria."""

        self.client.login(username="solicitante", password="123")
        saida = self._saida_base(days=4)
        retorno = saida + timedelta(hours=4)

        response = self.client.post(
            reverse("reserva_carros:solicitacao_create"),
            data={
                "saida_planejada_em": saida.strftime("%Y-%m-%dT%H:%M"),
                "retorno_planejado_em": retorno.strftime("%Y-%m-%dT%H:%M"),
                "destino_endereco": "Rua da Consolação, 123, São Paulo/SP",
                "modo_destino": ReservaCarro.ModoDestino.AGUARDAR_NO_LOCAL,
                "motivo_viagem": "Fiscalização externa",
                "observacoes_solicitante": "Levar documentos do processo.",
                "passageiros": [self.outro.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        reserva = ReservaCarro.objects.latest("id")
        destino = MensagemDestino.objects.filter(usuario=self.fiscal).latest("id")

        self.assertEqual(destino.mensagem.payload_email["tipo"], "nova_solicitacao_reserva_carro")
        self.assertEqual(destino.mensagem.payload_email["reserva_id"], reserva.pk)
        self.assertIn("link_analise", destino.mensagem.payload_email)
        self.assertNotIn("Analisar solicitação:", destino.corpo_snapshot)
        self.assertIn(str(reserva.pk), destino.assunto_snapshot)

    def test_solicitante_acessa_apenas_suas_solicitacoes(self):
        reserva_1 = self._reserva()
        self._reserva(solicitante=self.outro)
        self.client.login(username="solicitante", password="123")

        response = self.client.get(reverse("reserva_carros:solicitacao_list"))

        self.assertContains(response, f"#{reserva_1.pk}")
        self.assertNotContains(response, "Bianca")

    def test_usuario_sem_grupo_fiscal_nao_acessa_fila(self):
        self.client.login(username="solicitante", password="123")

        response = self.client.get(reverse("reserva_carros:fila_fiscal"))

        self.assertEqual(response.status_code, 403)

    def test_fiscal_acessa_fila_e_pode_analisar(self):
        reserva = self._reserva()
        self.client.login(username="fiscal", password="123")

        response = self.client.get(reverse("reserva_carros:fila_fiscal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"#{reserva.pk}")

        analise_response = self.client.post(
            reverse("reserva_carros:fila_fiscal_analise", args=[reserva.pk]),
            data={
                "decisao": "DEFERIR",
                "deslocamento_ida_minutos": 20,
                "deslocamento_retorno_minutos": 20,
                "carro": self.carro.pk,
                "motorista": self.motorista.pk,
                "justificativa_indeferimento": "",
            },
        )
        reserva.refresh_from_db()

        self.assertEqual(analise_response.status_code, 302)
        self.assertEqual(reserva.status, ReservaCarro.Status.DEFERIDA)

    def test_controle_total_acessa_carros_motoristas_e_configuracao(self):
        self.client.login(username="admin-carros", password="123")

        for url_name in ["carro_list", "motorista_list", "configuracao"]:
            response = self.client.get(reverse(f"reserva_carros:{url_name}"))
            self.assertEqual(response.status_code, 200)

    def test_agenda_exibe_botao_configuracao_para_controle_total(self):
        """A agenda principal deve expor o atalho de configuração no mesmo fluxo da garagem."""

        self.client.login(username="admin-carros", password="123")

        response = self.client.get(reverse("reserva_carros:agenda"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("reserva_carros:configuracao"))

    def test_controle_total_exclui_carro_e_motorista(self):
        self.client.login(username="admin-carros", password="123")
        carro = Carro.objects.create(marca="Fiat", modelo="Pulse", placa="XYZ9K88")
        motorista = Motorista.objects.create(nome_completo="Motorista Temporário")

        resposta_carro = self.client.post(reverse("reserva_carros:carro_delete", kwargs={"pk": carro.pk}))
        resposta_motorista = self.client.post(reverse("reserva_carros:motorista_delete", kwargs={"pk": motorista.pk}))

        self.assertRedirects(resposta_carro, reverse("reserva_carros:carro_list"))
        self.assertRedirects(resposta_motorista, reverse("reserva_carros:motorista_list"))
        self.assertFalse(Carro.objects.filter(pk=carro.pk).exists())
        self.assertFalse(Motorista.objects.filter(pk=motorista.pk).exists())

    def test_nova_solicitacao_preenche_data_quando_vem_da_agenda(self):
        self.client.login(username="solicitante", password="123")
        data_escolhida = self._saida_base(days=5).date().isoformat()

        response = self.client.get(reverse("reserva_carros:solicitacao_create"), {"data": data_escolhida})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{data_escolhida}T09:00"', html=False)
        self.assertContains(response, f'value="{data_escolhida}T18:00"', html=False)

    def test_detalhe_exibe_nome_em_vez_do_login_no_historico(self):
        """O histórico deve mostrar o nome do usuário responsável pela ação, não o username."""

        reserva = self._reserva()
        self.client.login(username="solicitante", password="123")
        self.client.post(
            reverse("reserva_carros:solicitacao_cancel", args=[reserva.pk]),
        )

        response = self.client.get(reverse("reserva_carros:solicitacao_detail", args=[reserva.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana")
        self.assertNotContains(response, "<p>solicitante</p>", html=False)

    def test_agenda_renderiza_viagem_multidia(self):
        saida = self._saida_base()
        reserva = self._reserva(saida_planejada_em=saida, retorno_planejado_em=saida + timedelta(days=1, hours=3))
        deferir_reserva(
            reserva,
            fiscal=self.fiscal,
            carro=self.carro,
            motorista=self.motorista,
            deslocamento_ida_minutos=10,
            deslocamento_retorno_minutos=15,
        )
        self.client.login(username="solicitante", password="123")

        response = self.client.get(reverse("reserva_carros:agenda"))

        self.assertContains(response, "viagens-data")
        self.assertContains(response, f'"id": {reserva.pk}', html=False)

    def test_agenda_renderiza_pendentes_em_cinza_e_oculta_indeferidas(self):
        pendente = self._reserva()
        indeferida = self._reserva(
            solicitante=self.outro,
            status=ReservaCarro.Status.INDEFERIDA,
            justificativa_indeferimento="Conflito operacional",
        )
        self.client.login(username="solicitante", password="123")

        response = self.client.get(reverse("reserva_carros:agenda"))

        self.assertContains(response, f'"id": {pendente.pk}', html=False)
        self.assertContains(response, '"cor": "#9ca3af"', html=False)
        self.assertContains(response, '"status_label": "Aguardando aprova\\u00e7\\u00e3o"', html=False)
        self.assertNotContains(response, f'"id": {indeferida.pk}', html=False)
