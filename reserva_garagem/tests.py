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
from mensageria_assincrona.models import Mensagem, MensagemDestino
from usuarios.models import UsuarioPerfil

from .forms import ReservaGaragemAnaliseForm, ReservaGaragemSolicitacaoForm
from .models import ConfiguracaoReservaGaragem, ReservaGaragem, ReservaGaragemEvento, VagaGaragem
from .services import cancelar_reserva, cancelar_reserva_com_escopo, deferir_reserva, indeferir_reserva


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

    def test_form_filtra_vagas_disponiveis_pelo_periodo(self):
        """A lista de vagas deve esconder apenas as que já estão deferidas no intervalo."""

        inicio = self._data_base()
        fim = inicio + timedelta(days=1)
        self._reserva(data=inicio, status=ReservaGaragem.Status.DEFERIDA, vaga=self.vaga_a, placa_veiculo="AAA1A11")
        self._reserva(
            data=fim,
            status=ReservaGaragem.Status.DEFERIDA,
            vaga=self.vaga_a,
            placa_veiculo="AAA1A12",
            solicitante=self.outro,
        )

        form = ReservaGaragemSolicitacaoForm(
            initial={"data_inicial": inicio, "data_final": fim},
            request_user=self.solicitante,
        )

        self.assertEqual(list(form.fields["vaga"].queryset), [self.vaga_b])
        self.assertTrue(form.tem_periodo_informado)
        self.assertTrue(form.tem_vagas_disponiveis)

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
    def test_criacao_notifica_fiscal_sem_exibir_link_no_corpo(self, criar_mensagem, publicar_mensagem):
        """A mensagem fiscal deve usar o payload para redirecionar o modal, sem poluir o corpo."""

        self.client.login(username="solicitante", password="123")
        data = self._data_base(days=4)

        response = self.client.post(
            reverse("reserva_garagem:reserva_create"),
            data=self._form_data(data_inicial=data, data_final=data),
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(criar_mensagem.called)
        self.assertTrue(publicar_mensagem.called)
        self.assertNotIn("Analisar solicitação:", criar_mensagem.call_args.kwargs["corpo"])
        self.assertIn("link_analise", criar_mensagem.call_args.kwargs["payload_email"])

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
        """O solicitante pode cancelar uma série pendente."""

        reserva = self._reserva()
        cancelar_reserva(reserva, usuario=self.solicitante)
        reserva.refresh_from_db()

        self.assertEqual(reserva.status, ReservaGaragem.Status.CANCELADA)

    def test_cancelamento_deferido_tambem_notifica_solicitante(self):
        """Reservas deferidas também podem ser canceladas, liberando a vaga e avisando o solicitante."""

        reserva = self._reserva(status=ReservaGaragem.Status.DEFERIDA, fiscal_responsavel=self.fiscal)
        cancelar_reserva(reserva, usuario=self.admin)
        reserva.refresh_from_db()

        self.assertEqual(reserva.status, ReservaGaragem.Status.CANCELADA)
        mensagem = Mensagem.objects.exclude(destinos__usuario=self.admin).latest("id")
        self.assertIn("Reserva de vaga cancelada", mensagem.assunto)
        self.assertEqual(
            list(mensagem.destinos.order_by("usuario_id").values_list("usuario_id", flat=True)),
            [self.solicitante.id],
        )

    def test_cancelamento_com_escopo_total_cancela_toda_a_serie(self):
        """O escopo total deve cancelar todas as ocorrências da série."""

        serie_id = uuid.uuid4()
        data_base = self._data_base()
        reserva_a = self._reserva(data=data_base, serie_id=serie_id)
        reserva_b = self._reserva(data=data_base + timedelta(days=1), serie_id=serie_id, placa_veiculo="AAA1A12")
        self._reserva(data=data_base + timedelta(days=2), serie_id=serie_id, placa_veiculo="AAA1A13")

        cancelar_reserva_com_escopo(reserva_a, usuario=self.solicitante, apply_scope="all")

        self.assertEqual(
            ReservaGaragem.objects.filter(serie_id=serie_id, status=ReservaGaragem.Status.CANCELADA).count(),
            3,
        )
        reserva_b.refresh_from_db()
        self.assertEqual(reserva_b.status, ReservaGaragem.Status.CANCELADA)

    def test_cancelamento_com_escopo_total_ignora_ocorrencias_ja_quebradas(self):
        """Ao cancelar toda a série, ocorrências já canceladas antes não devem bloquear o restante ativo."""

        serie_id = uuid.uuid4()
        data_base = self._data_base()
        reserva_a = self._reserva(data=data_base, serie_id=serie_id)
        reserva_b = self._reserva(
            data=data_base + timedelta(days=1),
            serie_id=serie_id,
            placa_veiculo="AAA1A12",
            status=ReservaGaragem.Status.CANCELADA,
        )
        reserva_c = self._reserva(
            data=data_base + timedelta(days=2),
            serie_id=serie_id,
            placa_veiculo="AAA1A13",
            status=ReservaGaragem.Status.DEFERIDA,
        )

        cancelar_reserva_com_escopo(
            reserva_a,
            usuario=self.solicitante,
            apply_scope="all",
            motivo_cancelamento="Cancelamento do período remanescente.",
        )

        reserva_a.refresh_from_db()
        reserva_b.refresh_from_db()
        reserva_c.refresh_from_db()
        self.assertEqual(reserva_a.status, ReservaGaragem.Status.CANCELADA)
        self.assertEqual(reserva_b.status, ReservaGaragem.Status.CANCELADA)
        self.assertEqual(reserva_c.status, ReservaGaragem.Status.CANCELADA)

    def test_cancelamento_com_periodo_especifico_cancela_so_faixa_informada(self):
        """O escopo por período deve cancelar apenas as datas contidas no intervalo informado."""

        serie_id = uuid.uuid4()
        data_base = self._data_base()
        primeira = self._reserva(data=data_base, serie_id=serie_id)
        meio = self._reserva(data=data_base + timedelta(days=1), serie_id=serie_id, placa_veiculo="AAA1A12")
        ultima = self._reserva(data=data_base + timedelta(days=2), serie_id=serie_id, placa_veiculo="AAA1A13")

        cancelar_reserva_com_escopo(
            primeira,
            usuario=self.solicitante,
            apply_scope="range",
            data_inicial=meio.data,
            data_final=ultima.data,
        )

        primeira.refresh_from_db()
        meio.refresh_from_db()
        ultima.refresh_from_db()
        self.assertEqual(primeira.status, ReservaGaragem.Status.AGUARDANDO_APROVACAO)
        self.assertEqual(meio.status, ReservaGaragem.Status.CANCELADA)
        self.assertEqual(ultima.status, ReservaGaragem.Status.CANCELADA)

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

    def _ocupar_agenda(self, response):
        """Indexa a ocupação retornada pela agenda para facilitar asserções por dia e vaga."""

        return {
            (item["data"], item["vaga_id"]): item
            for item in response.context["ocupacoes_data"]
        }

    def test_agenda_renderiza_um_circulo_por_vaga_em_cada_dia(self):
        """A agenda deve expor a lista completa de vagas ativas para a malha diária de círculos."""

        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))

        self.assertContains(response, "vagas-data")
        self.assertContains(response, "ocupacoes-data")
        self.assertEqual(
            [item["id"] for item in response.context["vagas_data"]],
            [self.vaga_a.id, self.vaga_b.id],
        )

    def test_agenda_marca_pendente_e_deferida_como_ocupadas(self):
        """Pendência e deferimento ocupam a vaga no calendário consolidado."""

        data = self._data_base()
        self._reserva(data=data, vaga=self.vaga_a, status=ReservaGaragem.Status.AGUARDANDO_APROVACAO)
        self._reserva(
            data=data,
            vaga=self.vaga_b,
            status=ReservaGaragem.Status.DEFERIDA,
            placa_veiculo="DEF3R11",
            solicitante=self.outro,
        )
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))
        ocupacoes = self._ocupar_agenda(response)

        self.assertTrue(ocupacoes[(data.isoformat(), self.vaga_a.id)]["occupied"])
        self.assertTrue(ocupacoes[(data.isoformat(), self.vaga_b.id)]["occupied"])

    def test_agenda_nao_cria_ocupacao_quando_vaga_esta_livre(self):
        """Vaga sem reserva no dia permanece ausente do mapa de ocupação e vira círculo verde no front."""

        data = self._data_base()
        self._reserva(data=data, vaga=self.vaga_a, status=ReservaGaragem.Status.DEFERIDA)
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))
        ocupacoes = self._ocupar_agenda(response)

        self.assertIn((data.isoformat(), self.vaga_a.id), ocupacoes)
        self.assertNotIn((data.isoformat(), self.vaga_b.id), ocupacoes)

    def test_agenda_destaca_is_mine_apenas_para_reserva_do_usuario_logado(self):
        """O anel azul deve aparecer somente quando a ocupação do dia pertence ao usuário autenticado."""

        data = self._data_base()
        self._reserva(data=data, vaga=self.vaga_a, solicitante=self.solicitante, status=ReservaGaragem.Status.DEFERIDA)
        self._reserva(
            data=data,
            vaga=self.vaga_b,
            solicitante=self.outro,
            status=ReservaGaragem.Status.DEFERIDA,
            placa_veiculo="ZZZ9Z99",
        )
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))
        ocupacoes = self._ocupar_agenda(response)

        self.assertTrue(ocupacoes[(data.isoformat(), self.vaga_a.id)]["is_mine"])
        self.assertFalse(ocupacoes[(data.isoformat(), self.vaga_b.id)]["is_mine"])

    def test_agenda_exibe_todas_as_reservas_nominalmente_para_fiscal(self):
        """Fiscais devem enxergar o nome responsável em qualquer vaga ocupada no tooltip."""

        data = self._data_base()
        self._reserva(data=data, vaga=self.vaga_a, solicitante=self.solicitante, status=ReservaGaragem.Status.DEFERIDA, responsavel="Ana")
        self._reserva(
            data=data,
            vaga=self.vaga_b,
            solicitante=self.outro,
            status=ReservaGaragem.Status.DEFERIDA,
            placa_veiculo="NOM1N11",
            responsavel="Bianca",
        )
        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))
        ocupacoes = self._ocupar_agenda(response)

        self.assertEqual(ocupacoes[(data.isoformat(), self.vaga_a.id)]["tooltip_label"], f"Ana, {self.vaga_a.nome_exibicao}")
        self.assertEqual(ocupacoes[(data.isoformat(), self.vaga_b.id)]["tooltip_label"], f"Bianca, {self.vaga_b.nome_exibicao}")
        self.assertTrue(ocupacoes[(data.isoformat(), self.vaga_a.id)]["detail_url"])
        self.assertTrue(ocupacoes[(data.isoformat(), self.vaga_b.id)]["detail_url"])

    def test_agenda_exibe_nome_apenas_na_propria_reserva_para_usuario_comum(self):
        """Cliente comum deve ver outras vagas só como ocupadas e a própria nominalmente."""

        data = self._data_base()
        self._reserva(data=data, vaga=self.vaga_a, solicitante=self.solicitante, status=ReservaGaragem.Status.DEFERIDA, responsavel="Ana")
        self._reserva(
            data=data,
            vaga=self.vaga_b,
            solicitante=self.outro,
            status=ReservaGaragem.Status.DEFERIDA,
            placa_veiculo="CLI2C22",
            responsavel="Bianca",
        )
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))
        ocupacoes = self._ocupar_agenda(response)

        self.assertEqual(ocupacoes[(data.isoformat(), self.vaga_a.id)]["tooltip_label"], f"Ana, {self.vaga_a.nome_exibicao}")
        self.assertEqual(ocupacoes[(data.isoformat(), self.vaga_b.id)]["tooltip_label"], "Ocupada")
        self.assertTrue(ocupacoes[(data.isoformat(), self.vaga_a.id)]["detail_url"])
        self.assertEqual(ocupacoes[(data.isoformat(), self.vaga_b.id)]["detail_url"], "")

    def test_agenda_filtra_para_uma_unica_vaga(self):
        """Ao filtrar por vaga, o contexto mantém a vaga atual e a interface renderiza só aquele círculo."""

        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"), data={"vaga": self.vaga_b.id})

        self.assertEqual(response.context["vaga_atual"], str(self.vaga_b.id))
        self.assertContains(response, f'value="{self.vaga_b.id}" selected')

    def test_agenda_exibe_botao_de_vaga_pre_reservada_para_fiscal(self):
        """O atalho da reserva pré-definida deve aparecer somente para quem atua no fluxo fiscal."""

        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))

        self.assertContains(response, reverse("reserva_garagem:reserva_predefinida_create"))

    def test_agenda_omite_botao_de_vaga_pre_reservada_para_solicitante_comum(self):
        """Usuário sem papel fiscal não deve visualizar o atalho operacional."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))

        self.assertNotContains(response, reverse("reserva_garagem:reserva_predefinida_create"))

    def test_agenda_exibe_botao_minhas_reservas_para_usuario_solicitante(self):
        """O calendário deve oferecer acesso rápido à listagem pessoal de reservas."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))

        self.assertContains(response, reverse("reserva_garagem:minhas_reservas"))

    def test_agenda_omite_indeferidas_e_canceladas(self):
        """Somente pendentes e deferidas ficam visíveis no calendário."""

        data = self._data_base()
        self._reserva(data=data, status=ReservaGaragem.Status.INDEFERIDA, placa_veiculo="IND1E00")
        self._reserva(data=data, status=ReservaGaragem.Status.CANCELADA, placa_veiculo="CAN1C00", vaga=self.vaga_b)
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:agenda"))
        ocupacoes = self._ocupar_agenda(response)

        self.assertNotIn((data.isoformat(), self.vaga_a.id), ocupacoes)
        self.assertNotIn((data.isoformat(), self.vaga_b.id), ocupacoes)

    def test_fila_fiscal_restrita_a_fiscais_e_admins_do_sistema(self):
        """Usuário comum não deve acessar a fila de deferimento."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:fila_fiscal"))

        self.assertEqual(response.status_code, 403)

    def test_crud_de_vagas_restrito_a_fiscais_e_admins(self):
        """O cadastro da garagem fica restrito ao grupo fiscal e ao perfil administrativo."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:vaga_list"))
        self.assertEqual(response.status_code, 403)

        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_garagem:vaga_list"))
        self.assertEqual(response.status_code, 200)

        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:vaga_list"))
        self.assertEqual(response.status_code, 200)

    def test_configuracao_restrita_a_fiscais_e_admins(self):
        """A configuração do grupo fiscal também deve abrir para fiscal e admin, mas não para cliente comum."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:configuracao"))
        self.assertEqual(response.status_code, 403)

        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_garagem:configuracao"))
        self.assertEqual(response.status_code, 200)

        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:configuracao"))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_renderiza_ocupacao_media_e_ranking(self):
        """O painel deve expor a taxa média diária e o ranking de vagas."""

        self._reserva(status=ReservaGaragem.Status.DEFERIDA, data=self._data_base(), placa_veiculo="DDD4D44")
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:dashboard"))

        self.assertContains(response, "Taxa média diária de ocupação")
        self.assertContains(response, "Ranking das vagas mais usadas")

    def test_dashboard_fica_restrito_a_fiscais_e_admins_do_sistema(self):
        """Usuário comum não deve abrir o dashboard restrito da garagem."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_lista_ordena_por_solicitante(self):
        """A lista deve aceitar ordenação automática pelo nome do solicitante."""

        data = self._data_base()
        self._reserva(data=data, responsavel="Carlos", placa_veiculo="ORD1A11")
        self._reserva(
            data=data,
            responsavel="Ana",
            placa_veiculo="ORD1A12",
            solicitante=self.outro,
            vaga=self.vaga_b,
        )
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_list"), data={"ordenar_por": "solicitante"})

        reservas = list(response.context["reservas"])
        self.assertEqual([reserva.responsavel for reserva in reservas], ["Ana", "Carlos"])

    def test_lista_restrita_a_fiscais_e_admins_do_sistema(self):
        """A listagem tabular de reservas deve ficar restrita ao grupo fiscal e aos admins do sistema."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_list"))

        self.assertEqual(response.status_code, 403)

    def test_minhas_reservas_lista_apenas_reservas_do_usuario_logado(self):
        """A tela Minhas reservas deve isolar apenas as reservas do próprio solicitante."""

        data = self._data_base()
        minha = self._reserva(data=data, solicitante=self.solicitante, placa_veiculo="MIN1A11")
        self._reserva(data=data, solicitante=self.outro, placa_veiculo="OUT2B22", vaga=self.vaga_b)
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:minhas_reservas"))

        reservas = list(response.context["reservas"])
        self.assertEqual([reserva.pk for reserva in reservas], [minha.pk])
        self.assertContains(response, "Minhas reservas")

    def test_minhas_reservas_filtra_por_status(self):
        """Os botões de status devem filtrar a listagem pessoal conforme a situação da reserva."""

        data = self._data_base()
        self._reserva(data=data, solicitante=self.solicitante, status=ReservaGaragem.Status.DEFERIDA, placa_veiculo="DEF1E11")
        self._reserva(
            data=data + timedelta(days=1),
            solicitante=self.solicitante,
            status=ReservaGaragem.Status.INDEFERIDA,
            placa_veiculo="IND2F22",
            vaga=self.vaga_b,
        )
        self.client.login(username="solicitante", password="123")
        response = self.client.get(
            reverse("reserva_garagem:minhas_reservas"),
            data={"status": ReservaGaragem.Status.INDEFERIDA},
        )

        reservas = list(response.context["reservas"])
        self.assertEqual(len(reservas), 1)
        self.assertEqual(reservas[0].status, ReservaGaragem.Status.INDEFERIDA)

    def test_lista_ordena_por_vaga(self):
        """A lista deve aceitar ordenação automática pelo nome da vaga."""

        data = self._data_base()
        self._reserva(data=data, vaga=self.vaga_b, placa_veiculo="ORD2B21")
        self._reserva(
            data=data,
            vaga=self.vaga_a,
            placa_veiculo="ORD2B22",
            solicitante=self.outro,
        )
        self.client.login(username="admin-garagem", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_list"), data={"ordenar_por": "vaga"})

        reservas = list(response.context["reservas"])
        self.assertEqual([reserva.vaga.nome for reserva in reservas], ["Vaga A", "Vaga B"])

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

    def test_reserva_create_notifica_grupo_fiscal(self):
        """Cada nova solicitação deve gerar mensagem interna para os fiscais configurados."""

        self.client.login(username="solicitante", password="123")
        inicio = self._data_base()
        response = self.client.post(
            reverse("reserva_garagem:reserva_create"),
            data=self._form_data(data_inicial=inicio, data_final=inicio, placa_veiculo="FIS1C45"),
        )

        self.assertEqual(response.status_code, 302)
        reserva = ReservaGaragem.objects.get(placa_veiculo="FIS1C45")
        mensagem = Mensagem.objects.exclude(destinos__usuario=reserva.solicitante).latest("id")
        self.assertIn("Nova solicitação de reserva de garagem", mensagem.assunto)
        self.assertIn(reverse("reserva_garagem:fila_fiscal_analise", args=[reserva.pk]), mensagem.corpo)
        self.assertEqual(
            list(mensagem.destinos.order_by("usuario_id").values_list("usuario_id", flat=True)),
            [self.fiscal.id],
        )

    def test_reserva_create_serie_notifica_grupo_fiscal_com_link_da_primeira_ocorrencia(self):
        """Séries devem publicar uma única mensagem fiscal apontando para a ocorrência base de análise."""

        self.client.login(username="solicitante", password="123")
        inicio = self._data_base()
        fim = inicio + timedelta(days=2)
        response = self.client.post(
            reverse("reserva_garagem:reserva_create"),
            data=self._form_data(data_inicial=inicio, data_final=fim, placa_veiculo="SER9A88"),
        )

        self.assertEqual(response.status_code, 302)
        reservas = list(ReservaGaragem.objects.filter(placa_veiculo="SER9A88").order_by("data", "id"))
        mensagem = Mensagem.objects.exclude(destinos__usuario=self.solicitante).latest("id")
        self.assertIn(reverse("reserva_garagem:fila_fiscal_analise", args=[reservas[0].pk]), mensagem.corpo)
        self.assertIn(f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}", mensagem.corpo)

    def test_reserva_create_prefill_data_vinda_da_agenda(self):
        """A data clicada no calendário deve chegar pré-preenchida no formulário."""

        self.client.login(username="solicitante", password="123")
        inicio = self._data_base()

        response = self.client.get(reverse("reserva_garagem:reserva_create"), data={"data": inicio.isoformat()})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{inicio.isoformat()}"', count=2)

    def test_reserva_predefinida_exige_perfil_fiscal(self):
        """Somente o grupo fiscal e o controle total podem abrir o cadastro pré-definido."""

        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_predefinida_create"))

        self.assertEqual(response.status_code, 403)

    def test_reserva_predefinida_renderiza_campo_responsavel_com_sugestoes(self):
        """O formulário fiscal deve permitir escolher ou digitar manualmente o responsável no mesmo campo."""

        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_predefinida_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'list="reserva-garagem-responsaveis"', html=False)
        self.assertContains(response, "<datalist", html=False)
        self.assertContains(response, "Ana")

    def test_reserva_predefinida_cria_reserva_deferida_com_nome_manual(self):
        """Quando o fiscal digita um nome manual, a vaga nasce deferida e vinculada ao próprio fiscal."""

        self.client.login(username="fiscal", password="123")
        inicio = self._data_base()
        response = self.client.post(
            reverse("reserva_garagem:reserva_predefinida_create"),
            data=self._form_data(
                data_inicial=inicio,
                data_final=inicio,
                placa_veiculo="MAN4U44",
                responsavel="Visitante externo",
            ),
        )

        self.assertEqual(response.status_code, 302)
        reserva = ReservaGaragem.objects.get(placa_veiculo="MAN4U44")
        self.assertEqual(reserva.status, ReservaGaragem.Status.DEFERIDA)
        self.assertEqual(reserva.fiscal_responsavel, self.fiscal)
        self.assertEqual(reserva.responsavel, "Visitante externo")
        self.assertEqual(reserva.solicitante, self.fiscal)

    def test_reserva_predefinida_resolve_usuario_cadastrado_pelo_nome(self):
        """Quando o nome informado coincidir com um usuário existente, ele vira o solicitante da reserva."""

        self.client.login(username="fiscal", password="123")
        inicio = self._data_base()
        response = self.client.post(
            reverse("reserva_garagem:reserva_predefinida_create"),
            data=self._form_data(
                data_inicial=inicio,
                data_final=inicio,
                placa_veiculo="USR5A55",
                responsavel="Ana",
            ),
        )

        self.assertEqual(response.status_code, 302)
        reserva = ReservaGaragem.objects.get(placa_veiculo="USR5A55")
        self.assertEqual(reserva.status, ReservaGaragem.Status.DEFERIDA)
        self.assertEqual(reserva.solicitante, self.solicitante)
        self.assertEqual(reserva.responsavel, "Ana")

    def test_api_vagas_disponiveis_retorna_somente_livres(self):
        """O endpoint auxiliar deve listar apenas as vagas sem conflito deferido."""

        self.client.login(username="solicitante", password="123")
        inicio = self._data_base()
        self._reserva(data=inicio, status=ReservaGaragem.Status.DEFERIDA, vaga=self.vaga_a, placa_veiculo="GGG7G77")

        response = self.client.get(
            reverse("reserva_garagem:vagas_disponiveis"),
            data={"data_inicial": inicio.isoformat(), "data_final": inicio.isoformat(), "recorrencia": ""},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["tem_vagas"])
        self.assertEqual(payload["vagas"], [{"id": self.vaga_b.id, "nome_exibicao": self.vaga_b.nome_exibicao}])

    def test_api_vagas_disponiveis_tambem_libera_fluxo_fiscal_predefinido(self):
        """O fiscal precisa usar o mesmo endpoint para escolher a vaga livre da reserva pré-definida."""

        self.client.login(username="fiscal", password="123")
        inicio = self._data_base()
        self._reserva(data=inicio, status=ReservaGaragem.Status.DEFERIDA, vaga=self.vaga_a, placa_veiculo="FSC1A11")

        response = self.client.get(
            reverse("reserva_garagem:vagas_disponiveis"),
            data={"data_inicial": inicio.isoformat(), "data_final": inicio.isoformat(), "recorrencia": ""},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["tem_vagas"])
        self.assertEqual(payload["vagas"], [{"id": self.vaga_b.id, "nome_exibicao": self.vaga_b.nome_exibicao}])

    def test_api_vagas_disponiveis_informa_quando_nao_ha_vaga(self):
        """A interface precisa receber uma mensagem clara quando o período estiver lotado."""

        self.client.login(username="solicitante", password="123")
        inicio = self._data_base()
        self._reserva(data=inicio, status=ReservaGaragem.Status.DEFERIDA, vaga=self.vaga_a, placa_veiculo="HHH8H88")
        self._reserva(
            data=inicio,
            status=ReservaGaragem.Status.DEFERIDA,
            vaga=self.vaga_b,
            placa_veiculo="III9I99",
            solicitante=self.outro,
        )

        response = self.client.get(
            reverse("reserva_garagem:vagas_disponiveis"),
            data={"data_inicial": inicio.isoformat(), "data_final": inicio.isoformat(), "recorrencia": ""},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["tem_vagas"])
        self.assertEqual(payload["mensagem"], f"Não há vagas para o período de {inicio:%d/%m/%Y} a {inicio:%d/%m/%Y}")

    def test_detalhe_exibe_nome_em_vez_do_login_no_historico(self):
        """O histórico da reserva deve mostrar o nome do usuário responsável pela ação."""

        reserva = self._reserva()
        self.client.login(username="solicitante", password="123")
        self.client.post(reverse("reserva_garagem:reserva_cancel", args=[reserva.pk]))

        response = self.client.get(reverse("reserva_garagem:reserva_detail", args=[reserva.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ana")
        self.assertNotContains(response, "<p>solicitante</p>", html=False)

    def test_detalhe_exibe_cancelar_na_propria_reserva_para_usuario_comum(self):
        """O solicitante deve ver o botão de cancelar na própria reserva ativa."""

        reserva = self._reserva(status=ReservaGaragem.Status.DEFERIDA)
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_detail", args=[reserva.pk]))

        self.assertContains(response, reverse("reserva_garagem:reserva_cancel", args=[reserva.pk]))

    def test_detalhe_exibe_cancelar_em_qualquer_reserva_para_fiscal(self):
        """Fiscal deve poder cancelar qualquer reserva ativa a partir do detalhe."""

        reserva = self._reserva(status=ReservaGaragem.Status.DEFERIDA, solicitante=self.outro, placa_veiculo="FIS9C99")
        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_detail", args=[reserva.pk]))

        self.assertContains(response, reverse("reserva_garagem:reserva_cancel", args=[reserva.pk]))

    def test_cancelamento_view_libera_fiscal_para_reserva_de_terceiro(self):
        """Fiscal pode cancelar reserva ativa de outro usuário e a reserva deixa de ocupar a vaga."""

        data = self._data_base()
        reserva = self._reserva(
            data=data,
            status=ReservaGaragem.Status.DEFERIDA,
            solicitante=self.outro,
            placa_veiculo="LIV3R33",
        )
        self.client.login(username="fiscal", password="123")
        response = self.client.post(reverse("reserva_garagem:reserva_cancel", args=[reserva.pk]))

        self.assertEqual(response.status_code, 302)
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, ReservaGaragem.Status.CANCELADA)

        agenda = self.client.get(reverse("reserva_garagem:agenda"))
        ocupacoes = self._ocupar_agenda(agenda)
        self.assertNotIn((data.isoformat(), reserva.vaga_id), ocupacoes)

    def test_cancelamento_view_exibe_opcoes_de_serie(self):
        """A tela de cancelamento deve permitir escolher ocorrência única, série toda ou período específico."""

        serie_id = uuid.uuid4()
        reserva = self._reserva(serie_id=serie_id)
        self._reserva(data=self._data_base() + timedelta(days=1), serie_id=serie_id, placa_veiculo="SER1E11")
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:reserva_cancel", args=[reserva.pk]))

        self.assertContains(response, "Cancelar todo o período")
        self.assertContains(response, "Cancelar período específico")
        self.assertContains(response, 'name="cancel_data_inicial"', html=False)

    def test_cancelamento_view_aceita_periodo_especifico(self):
        """O POST da tela deve cancelar apenas o intervalo selecionado dentro da série."""

        serie_id = uuid.uuid4()
        data_base = self._data_base()
        primeira = self._reserva(data=data_base, serie_id=serie_id)
        meio = self._reserva(data=data_base + timedelta(days=1), serie_id=serie_id, placa_veiculo="SER2E12")
        ultima = self._reserva(data=data_base + timedelta(days=2), serie_id=serie_id, placa_veiculo="SER2E13")
        self.client.login(username="solicitante", password="123")
        response = self.client.post(
            reverse("reserva_garagem:reserva_cancel", args=[primeira.pk]),
            data={
                "apply_scope": "range",
                "cancel_data_inicial": meio.data.isoformat(),
                "cancel_data_final": ultima.data.isoformat(),
            },
        )

        self.assertEqual(response.status_code, 302)
        primeira.refresh_from_db()
        meio.refresh_from_db()
        ultima.refresh_from_db()
        self.assertEqual(primeira.status, ReservaGaragem.Status.AGUARDANDO_APROVACAO)
        self.assertEqual(meio.status, ReservaGaragem.Status.CANCELADA)
        self.assertEqual(ultima.status, ReservaGaragem.Status.CANCELADA)

    def test_analise_indeferimento_exige_fiscal(self):
        """A tela de análise deve bloquear quem não pertence ao fluxo fiscal."""

        reserva = self._reserva()
        self.client.login(username="solicitante", password="123")
        response = self.client.get(reverse("reserva_garagem:fila_fiscal_analise", args=[reserva.pk]))

        self.assertEqual(response.status_code, 403)

    def test_analise_exibe_reserva_ja_deferida_como_somente_leitura(self):
        """Reserva já decidida deve abrir em modo bloqueado, sem nova ação fiscal."""

        reserva = self._reserva(status=ReservaGaragem.Status.DEFERIDA, fiscal_responsavel=self.admin)
        self.client.login(username="fiscal", password="123")
        response = self.client.get(reverse("reserva_garagem:fila_fiscal_analise", args=[reserva.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Status atual:</strong> Deferida", html=False)
        self.assertContains(response, "bloqueada para nova análise")
        self.assertNotContains(response, "Salvar decisão")

    def test_analise_bloqueia_post_quando_reserva_ja_foi_decidida(self):
        """Mesmo com POST manual, a view não deve permitir nova decisão sobre reserva já deferida."""

        reserva = self._reserva(status=ReservaGaragem.Status.DEFERIDA, fiscal_responsavel=self.admin)
        self.client.login(username="fiscal", password="123")
        response = self.client.post(
            reverse("reserva_garagem:fila_fiscal_analise", args=[reserva.pk]),
            data={"decisao": "INDEFERIR", "justificativa_indeferimento": "Nova tentativa"},
            follow=True,
        )

        reserva.refresh_from_db()
        self.assertEqual(reserva.status, ReservaGaragem.Status.DEFERIDA)
        self.assertContains(response, "já foi deferida e não pode ser analisada novamente")

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
