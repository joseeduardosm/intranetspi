# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Validar cálculos críticos, ACL básica e exportação do módulo de contratos.

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from acls.models import Recurso, RegraAcesso

from .forms import ContratoForm
from .models import (
    AvaliacaoCriterioCompetencia,
    AvaliacaoQualidadeCompetencia,
    ChecklistPagamentoModelo,
    CompetenciaPagamento,
    Contrato,
    ContratoDetalhamentoItem,
    ContratoItem,
    CriterioAvaliacaoQualidade,
    EmpresaContratada,
    EventoFinanceiroContrato,
    EventoFinanceiroItem,
    GrupoAvaliacaoQualidade,
    MedicaoItemCompetencia,
    ModeloAvaliacaoQualidade,
    OcorrenciaContrato,
    TermoAditivo,
)


class ContratosBaseTest(TestCase):
    """Base compartilhada para instanciar usuários, ACL e contrato de teste."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin-contratos', password='123', is_staff=True)
        self.user = User.objects.create_user(username='joao', password='123')
        self.sem_acesso = User.objects.create_user(username='maria', password='123')
        self.recurso, _ = Recurso.objects.get_or_create(slug='contratos', defaults={'nome': 'Contratos'})
        RegraAcesso.objects.create(recurso=self.recurso, usuario=self.user, nivel=RegraAcesso.NIVEL_MODIFICACAO)
        self.empresa = EmpresaContratada.objects.create(razao_social='Empresa XPTO', cnpj='00.000.000/0001-00')
        self.contrato = Contrato.objects.create(
            numero_contrato='01/2026',
            apelido='Limpeza predial',
            objeto='Prestação de serviços de limpeza',
            detalhamento_objeto='Serviço contínuo.',
            data_inicio_vigencia=date(2026, 1, 1),
            prazo_inicial_meses=12,
            vigencia_maxima_meses=24,
            empresa_contratada=self.empresa,
            fiscal_administrativo=self.admin,
            fiscal_tecnico=self.admin,
            gestor_contrato=self.admin,
            base_mensal=Decimal('1000.00'),
            criado_por=self.admin,
            atualizado_por=self.admin,
        )


class ContratoCalculoTests(ContratosBaseTest):
    """Cobre cálculos estruturais de contrato, avaliação e retroatividade."""

    def test_calcula_subtotal_e_valor_global(self):
        ContratoItem.objects.create(
            contrato=self.contrato,
            ordem=1,
            descricao='Posto A',
            quantidade=Decimal('2.00'),
            valor_unitario=Decimal('150.00'),
        )
        ContratoItem.objects.create(
            contrato=self.contrato,
            ordem=2,
            descricao='Posto B',
            quantidade=Decimal('1.00'),
            valor_unitario=Decimal('100.00'),
        )

        self.contrato.refresh_from_db()
        self.assertEqual(self.contrato.valor_global, Decimal('400.00'))

    def test_calcula_vigencia_periodo_e_regime(self):
        TermoAditivo.objects.create(
            contrato=self.contrato,
            numero_termo='1º TA',
            tipo=TermoAditivo.Tipo.PRORROGACAO,
            data_assinatura=date(2026, 11, 1),
            data_inicio=date(2027, 1, 1),
            data_termino=date(2027, 12, 31),
            quantidade_meses=12,
        )
        self.assertEqual(self.contrato.regime_atual, Contrato.Regime.ORDINARIO)
        self.assertEqual(self.contrato.data_limite_vigencia.strftime('%d/%m/%Y'), '31/12/2027')
        self.assertIn('/24 meses', self.contrato.periodo_acumulado_display)

    def test_bloqueia_pagamento_com_checklist_incompleto(self):
        competencia = CompetenciaPagamento.objects.create(
            contrato=self.contrato,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
        )
        ChecklistPagamentoModelo.objects.create(contrato=self.contrato, ordem=1, titulo='NF', obrigatorio=True)
        competencia.delete()
        competencia = CompetenciaPagamento.objects.create(
            contrato=self.contrato,
            periodo_inicio=date(2026, 2, 1),
            periodo_fim=date(2026, 2, 28),
        )
        self.assertFalse(competencia.pode_liberar)

    def test_criacao_e_calculo_de_medicao(self):
        item = ContratoItem.objects.create(
            contrato=self.contrato,
            ordem=1,
            descricao='Item medido',
            quantidade=Decimal('10.00'),
            valor_unitario=Decimal('50.00'),
        )
        competencia = CompetenciaPagamento.objects.create(
            contrato=self.contrato,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
        )
        MedicaoItemCompetencia.objects.create(
            competencia=competencia,
            item_contrato=item,
            quantidade=Decimal('2.00'),
            valor_unitario_aplicado=Decimal('50.00'),
        )
        competencia.refresh_from_db()
        self.assertEqual(competencia.valor_medido, Decimal('100.00'))
        self.assertEqual(competencia.valor_liberado, Decimal('100.00'))

    def test_aplica_avaliacao_qualidade_ao_valor_final(self):
        item = ContratoItem.objects.create(
            contrato=self.contrato,
            ordem=1,
            descricao='Item qualidade',
            quantidade=Decimal('1.00'),
            valor_unitario=Decimal('100.00'),
        )
        competencia = CompetenciaPagamento.objects.create(
            contrato=self.contrato,
            periodo_inicio=date(2026, 3, 1),
            periodo_fim=date(2026, 3, 31),
        )
        MedicaoItemCompetencia.objects.create(
            competencia=competencia,
            item_contrato=item,
            quantidade=Decimal('1.00'),
            valor_unitario_aplicado=Decimal('100.00'),
        )
        modelo = ModeloAvaliacaoQualidade.objects.create(
            contrato=self.contrato,
            nome='SLA',
            vigencia_inicio=date(2026, 1, 1),
        )
        grupo = GrupoAvaliacaoQualidade.objects.create(modelo=modelo, ordem=1, nome='Desempenho', peso=Decimal('1.00'))
        criterio = CriterioAvaliacaoQualidade.objects.create(
            grupo=grupo,
            ordem=1,
            nome='Pontualidade',
            peso=Decimal('1.00'),
            pontuacao_maxima=Decimal('10.00'),
        )
        avaliacao = AvaliacaoQualidadeCompetencia.objects.create(competencia=competencia, modelo=modelo)
        AvaliacaoCriterioCompetencia.objects.create(avaliacao=avaliacao, criterio=criterio, nota_obtida=Decimal('8.00'))

        avaliacao.refresh_from_db()
        competencia.refresh_from_db()
        self.assertEqual(avaliacao.percentual_desempenho, Decimal('80.00'))
        self.assertEqual(competencia.valor_liberado, Decimal('80.00'))

    def test_reajuste_respeita_valor_referencial_e_calcula_retroatividade(self):
        item = ContratoItem.objects.create(
            contrato=self.contrato,
            ordem=1,
            descricao='Item reajustado',
            quantidade=Decimal('10.00'),
            valor_unitario=Decimal('90.00'),
            valor_referencial=Decimal('100.00'),
        )
        competencia = CompetenciaPagamento.objects.create(
            contrato=self.contrato,
            periodo_inicio=date(2026, 4, 1),
            periodo_fim=date(2026, 4, 30),
        )
        MedicaoItemCompetencia.objects.create(
            competencia=competencia,
            item_contrato=item,
            quantidade=Decimal('2.00'),
            valor_unitario_aplicado=Decimal('90.00'),
        )
        evento = EventoFinanceiroContrato.objects.create(
            contrato=self.contrato,
            tipo=EventoFinanceiroContrato.Tipo.REAJUSTE,
            indice_aplicado='IPCA',
            data_base=date(2026, 4, 1),
            data_aplicacao=date(2026, 5, 1),
            percentual_aplicado=Decimal('10.00'),
        )
        EventoFinanceiroItem.objects.create(
            evento=evento,
            item_contrato=item,
            valor_original=Decimal('90.00'),
            valor_reajustado=Decimal('99.00'),
            valor_referencial=Decimal('100.00'),
        )

        memoria = evento.memorias.get(competencia=competencia, item_contrato=item)
        self.assertEqual(memoria.diferenca_total, Decimal('18.00'))


class ContratosViewTests(ContratosBaseTest):
    """Valida ACL, filtros de listagem e exportação do diário de bordo."""

    def test_acl_bloqueia_usuario_sem_regra(self):
        self.client.login(username='maria', password='123')
        response = self.client.get(reverse('contratos:home'))
        self.assertEqual(response.status_code, 403)

    def test_listagem_filtra_por_texto(self):
        self.client.login(username='joao', password='123')
        response = self.client.get(reverse('contratos:contrato_list'), {'q': 'Limpeza'})
        self.assertContains(response, 'Limpeza predial')

    def test_exporta_diario_xlsx(self):
        OcorrenciaContrato.objects.create(
            contrato=self.contrato,
            data_registro=date(2026, 1, 10),
            tipo_ocorrencia='Fiscalização',
            descricao='Vistoria executada.',
            usuario=self.admin,
        )
        self.client.login(username='joao', password='123')
        response = self.client.get(reverse('contratos:ocorrencia_export_xlsx', args=[self.contrato.pk]))
        workbook = load_workbook(BytesIO(response.content))
        ws = workbook.active
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ws['A1'].value, 'Número do Contrato')
        self.assertEqual(ws['B1'].value, '01/2026')
        self.assertEqual(ws['A6'].value, 'Data')

    def test_formulario_gera_numero_incremental_no_mesmo_ano(self):
        self.client.login(username='joao', password='123')
        Contrato.objects.create(
            numero_contrato='070/2026',
            apelido='Outro contrato',
            objeto='Objeto auxiliar',
            detalhamento_objeto='Detalhamento.',
            data_inicio_vigencia=date(2026, 2, 1),
            prazo_inicial_meses=12,
            vigencia_maxima_meses=24,
            empresa_contratada=self.empresa,
            fiscal_administrativo=self.admin,
            fiscal_tecnico=self.admin,
            gestor_contrato=self.admin,
            base_mensal=Decimal('500.00'),
            criado_por=self.admin,
            atualizado_por=self.admin,
        )

        response = self.client.post(
            reverse('contratos:contrato_create'),
            {
                'numero_contrato': '',
                'numero_contrato_incremental': 'on',
                'apelido': 'Contrato incremental',
                'objeto': 'Objeto incremental',
                'detalhamento_objeto': 'Detalhamento.',
                'data_inicio_vigencia': '2026-06-01',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'fiscal_administrativo': str(self.admin.pk),
                'fiscal_tecnico': str(self.admin.pk),
                'gestor_contrato': str(self.admin.pk),
                'base_mensal': '1000.00',
                'situacao_forcada': '',
                'detalhamento-TOTAL_FORMS': '0',
                'detalhamento-INITIAL_FORMS': '0',
                'detalhamento-MIN_NUM_FORMS': '0',
                'detalhamento-MAX_NUM_FORMS': '1000',
            },
        )

        criado = Contrato.objects.get(apelido='Contrato incremental')
        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[criado.pk]), fetch_redirect_response=False)
        self.assertEqual(criado.numero_contrato, '071/2026')

    def test_formulario_incremental_reinicia_sequencia_em_novo_ano(self):
        form = ContratoForm(
            data={
                'numero_contrato': '',
                'numero_contrato_incremental': 'on',
                'apelido': 'Virada de ano',
                'objeto': 'Objeto',
                'detalhamento_objeto': 'Detalhamento.',
                'data_inicio_vigencia': '2027-01-15',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'fiscal_administrativo': str(self.admin.pk),
                'fiscal_tecnico': str(self.admin.pk),
                'gestor_contrato': str(self.admin.pk),
                'base_mensal': '1000.00',
                'situacao_forcada': '',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['numero_contrato'], '001/2027')

    def test_formulario_valida_formato_manual_do_numero(self):
        form = ContratoForm(
            data={
                'numero_contrato': '1/2026',
                'apelido': 'Manual inválido',
                'objeto': 'Objeto',
                'detalhamento_objeto': 'Detalhamento.',
                'data_inicio_vigencia': '2026-01-01',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'fiscal_administrativo': str(self.admin.pk),
                'fiscal_tecnico': str(self.admin.pk),
                'gestor_contrato': str(self.admin.pk),
                'base_mensal': '1000.00',
                'situacao_forcada': '',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('numero_contrato', form.errors)

    def test_criacao_de_contrato_salva_detalhamento_por_itens(self):
        self.client.login(username='joao', password='123')
        response = self.client.post(
            reverse('contratos:contrato_create'),
            {
                'numero_contrato': '',
                'numero_contrato_incremental': 'on',
                'apelido': 'Contrato com detalhamento',
                'objeto': 'Objeto detalhado',
                'data_inicio_vigencia': '2026-06-01',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'fiscal_administrativo': str(self.admin.pk),
                'fiscal_tecnico': str(self.admin.pk),
                'gestor_contrato': str(self.admin.pk),
                'base_mensal': '1000.00',
                'situacao_forcada': '',
                'detalhamento-TOTAL_FORMS': '2',
                'detalhamento-INITIAL_FORMS': '0',
                'detalhamento-MIN_NUM_FORMS': '0',
                'detalhamento-MAX_NUM_FORMS': '1000',
                'detalhamento-0-ordem': '1',
                'detalhamento-0-descricao': 'Primeiro item do detalhamento',
                'detalhamento-1-ordem': '2',
                'detalhamento-1-descricao': 'Segundo item do detalhamento',
            },
        )

        contrato = Contrato.objects.get(apelido='Contrato com detalhamento')
        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertEqual(contrato.detalhamento_itens.count(), 2)
        self.assertEqual(
            list(contrato.detalhamento_itens.order_by('ordem').values_list('descricao', flat=True)),
            ['Primeiro item do detalhamento', 'Segundo item do detalhamento'],
        )
        self.assertEqual(
            contrato.detalhamento_objeto,
            '1. Primeiro item do detalhamento\n2. Segundo item do detalhamento',
        )
