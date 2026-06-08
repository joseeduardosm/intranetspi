# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Cobrir o CRUD principal e o fluxo mensal de checklist, competências, medição, avaliação e pagamento do Contratos V2.

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from acls.models import Recurso, RegraAcesso
from contratos.models import EmpresaContratada

from .forms import (
    CompetenciaMedicaoLoteV2Form,
    ContratoV2Form,
    EscalaNotaAvaliacaoV2Form,
    FaixaLiberacaoAvaliacaoV2Form,
    GrupoAvaliacaoV2Form,
    ItemAvaliacaoV2Form,
)
from .models import (
    ChecklistModeloItemV2,
    ChecklistModeloV2,
    CompetenciaPagamentoV2,
    ContratoItemV2,
    ContratoV2,
    EscalaNotaAvaliacaoV2,
    FaixaLiberacaoAvaliacaoV2,
    FormularioAvaliacaoV2,
    GrupoAvaliacaoV2,
    ItemAvaliacaoV2,
)


User = get_user_model()


class ContratosV2Tests(TestCase):
    """Valida a evolução do módulo Contratos V2 para o fluxo completo de competências."""

    def setUp(self):
        self.gestor = User.objects.create_user(username='gestor_v2', password='123', is_staff=True)
        self.fiscal_adm = User.objects.create_user(username='fadm_v2', password='123')
        self.fiscal_tec = User.objects.create_user(username='ftec_v2', password='123')
        self.operador = User.objects.create_user(username='operador_v2', password='123')
        self.recurso, _ = Recurso.objects.get_or_create(slug='contratos_v2', defaults={'nome': 'Contratos V2'})
        regra = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_MODIFICACAO)
        regra.usuarios.add(self.gestor, self.fiscal_adm, self.fiscal_tec, self.operador)
        self.empresa = EmpresaContratada.objects.create(razao_social='Empresa V2', cnpj='11.111.111/0001-11')

    def criar_contrato(self, numero='001/2026', prazo=2):
        return ContratoV2.objects.create(
            numero_contrato=numero,
            apelido='Contrato teste',
            objeto='Serviço continuado',
            data_inicio_vigencia=date(2026, 1, 1),
            prazo_inicial_meses=prazo,
            vigencia_maxima_meses=24,
            empresa_contratada=self.empresa,
            fiscal_administrativo=self.fiscal_adm,
            fiscal_tecnico=self.fiscal_tec,
            gestor_contrato=self.gestor,
        )

    def criar_item_contrato(self, contrato, ordem=1, quantidade='10.00', unitario='100.00'):
        return ContratoItemV2.objects.create(
            contrato=contrato,
            ordem=ordem,
            descricao=f'Item {ordem}',
            quantidade=Decimal(quantidade),
            valor_unitario=Decimal(unitario),
        )

    def criar_checklist_ativo(self, contrato, nome='Checklist v1', titulo='FGTS'):
        checklist = ChecklistModeloV2.objects.create(
            contrato=contrato,
            nome=nome,
            descricao='Checklist da competência',
            ativo=True,
        )
        ChecklistModeloItemV2.objects.create(modelo=checklist, ordem=1, titulo=titulo, obrigatorio=True)
        return checklist

    def criar_formulario_avaliacao(self, contrato):
        formulario = FormularioAvaliacaoV2.objects.create(
            contrato=contrato,
            nome='Avaliação 2026',
            descricao='Modelo de qualidade',
            ativo=True,
        )
        EscalaNotaAvaliacaoV2.objects.create(formulario=formulario, ordem=1, valor=Decimal('0.00'), legenda='Insatisfatório')
        EscalaNotaAvaliacaoV2.objects.create(formulario=formulario, ordem=2, valor=Decimal('1.00'), legenda='Regular')
        EscalaNotaAvaliacaoV2.objects.create(formulario=formulario, ordem=3, valor=Decimal('3.00'), legenda='Bom')
        FaixaLiberacaoAvaliacaoV2.objects.create(
            formulario=formulario,
            ordem=1,
            nota_minima=Decimal('0.00'),
            nota_maxima=Decimal('1.99'),
            percentual_liberacao=Decimal('75.00'),
        )
        FaixaLiberacaoAvaliacaoV2.objects.create(
            formulario=formulario,
            ordem=2,
            nota_minima=Decimal('2.00'),
            nota_maxima=Decimal('2.99'),
            percentual_liberacao=Decimal('90.00'),
        )
        FaixaLiberacaoAvaliacaoV2.objects.create(
            formulario=formulario,
            ordem=3,
            nota_minima=Decimal('3.00'),
            percentual_liberacao=Decimal('100.00'),
        )
        grupo = GrupoAvaliacaoV2.objects.create(formulario=formulario, ordem=1, nome='Desempenho')
        ItemAvaliacaoV2.objects.create(grupo=grupo, ordem=1, descricao='Qualidade da entrega', peso_percentual=Decimal('100.00'))
        return formulario

    def test_formulario_gera_numero_incremental(self):
        self.criar_contrato(numero='001/2026')
        form = ContratoV2Form(
            data={
                'numero_contrato': '',
                'numero_contrato_incremental': 'on',
                'apelido': 'Contrato incremental',
                'objeto': 'Objeto incremental',
                'data_inicio_vigencia': '2026-06-01',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'fiscal_administrativo': str(self.fiscal_adm.pk),
                'fiscal_tecnico': str(self.fiscal_tec.pk),
                'gestor_contrato': str(self.gestor.pk),
                'situacao_forcada': '',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['numero_contrato'], '002/2026')

    def test_formulario_de_escala_nao_expoe_ordem(self):
        form = EscalaNotaAvaliacaoV2Form()

        self.assertNotIn('ordem', form.fields)

    def test_formulario_de_faixa_nao_expoe_ordem(self):
        form = FaixaLiberacaoAvaliacaoV2Form()

        self.assertNotIn('ordem', form.fields)

    def test_formulario_de_grupo_nao_expoe_ordem_nem_peso(self):
        form = GrupoAvaliacaoV2Form()

        self.assertNotIn('ordem', form.fields)
        self.assertNotIn('peso_percentual', form.fields)

    def test_formulario_de_item_nao_expoe_ordem(self):
        form = ItemAvaliacaoV2Form()

        self.assertNotIn('ordem', form.fields)

    def test_formulario_de_medicao_expoe_pro_rata_so_na_primeira_e_ultima_competencia(self):
        contrato = self.criar_contrato(prazo=3)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencias = list(contrato.competencias.order_by('periodo_inicio'))

        form_primeira = CompetenciaMedicaoLoteV2Form(contrato=contrato, competencia=competencias[0])
        form_intermediaria = CompetenciaMedicaoLoteV2Form(contrato=contrato, competencia=competencias[1])
        form_ultima = CompetenciaMedicaoLoteV2Form(contrato=contrato, competencia=competencias[2])

        self.assertIn('aplicar_pro_rata', form_primeira.fields)
        self.assertNotIn('aplicar_pro_rata', form_intermediaria.fields)
        self.assertIn('aplicar_pro_rata', form_ultima.fields)

    def test_medicao_persiste_checkbox_de_pro_rata(self):
        contrato = self.criar_contrato(prazo=2)
        item = self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato, titulo='Documento mensal')
        contrato.gerar_competencias()
        competencia = contrato.competencias.order_by('periodo_inicio').first()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos_v2:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', b'%PDF-1.4 doc', content_type='application/pdf')},
        )

        response = self.client.post(
            reverse('contratos_v2:competencia_medicao', args=[competencia.pk]),
            {
                'aplicar_pro_rata': 'on',
                f'quantidade_{item.pk}': '2.00',
            },
        )
        competencia.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(competencia.aplicar_pro_rata)

    def test_sem_checklist_ativo_nao_gera_competencias(self):
        contrato = self.criar_contrato()
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(reverse('contratos_v2:competencias_generate', args=[contrato.pk]))

        self.assertRedirects(response, reverse('contratos_v2:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertEqual(contrato.competencias.count(), 0)

    def test_gera_competencias_da_vigencia_e_nao_duplica(self):
        contrato = self.criar_contrato(prazo=2)
        self.criar_item_contrato(contrato, ordem=1, quantidade='1.00', unitario='100.00')
        self.criar_checklist_ativo(contrato)
        self.client.login(username='gestor_v2', password='123')

        url = reverse('contratos_v2:competencias_generate', args=[contrato.pk])
        self.client.post(url)
        self.client.post(url)

        competencias = list(contrato.competencias.order_by('periodo_inicio'))
        self.assertEqual(len(competencias), 2)
        self.assertEqual(competencias[0].periodo_inicio, date(2026, 1, 1))
        self.assertEqual(competencias[1].periodo_inicio, date(2026, 2, 1))
        self.assertEqual(competencias[0].status, CompetenciaPagamentoV2.Status.CHECKLIST_PENDENTE)

    def test_detalhe_renderiza_blocos_de_checklist_avaliacao_e_competencias(self):
        contrato = self.criar_contrato(prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos_v2:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Versões de checklist')
        self.assertContains(response, 'Formulários de avaliação')
        self.assertContains(response, 'Competências geradas')
        self.assertContains(response, 'Checklist')
        self.assertContains(response, 'Pagamento')

    def test_ativar_novo_checklist_atualiza_competencias_em_aberto(self):
        contrato = self.criar_contrato()
        self.criar_item_contrato(contrato)
        checklist_v1 = self.criar_checklist_ativo(contrato, nome='Checklist v1', titulo='FGTS')
        contrato.gerar_competencias()
        competencia = contrato.competencias.first()
        self.assertEqual(list(competencia.checklist_itens.values_list('titulo', flat=True)), ['FGTS'])

        checklist_v2 = ChecklistModeloV2.objects.create(
            contrato=contrato,
            nome='Checklist v2',
            descricao='Nova versão',
            ativo=True,
        )
        ChecklistModeloItemV2.objects.create(modelo=checklist_v2, ordem=1, titulo='INSS', obrigatorio=True)
        checklist_v1.refresh_from_db()
        competencia.refresh_from_db()

        self.assertFalse(checklist_v1.ativo)
        self.assertEqual(list(competencia.checklist_itens.values_list('titulo', flat=True)), ['INSS'])

    def test_fluxo_pagamento_sem_avaliacao(self):
        contrato = self.criar_contrato(prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato, titulo='Documento mensal')
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        checklist_url = reverse('contratos_v2:competencia_checklist', args=[competencia.pk])
        medicao_url = reverse('contratos_v2:competencia_medicao', args=[competencia.pk])
        pagamento_url = reverse('contratos_v2:competencia_pagamento', args=[competencia.pk])

        response_checklist = self.client.post(
            checklist_url,
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', b'%PDF-1.4 doc', content_type='application/pdf')},
        )
        self.assertEqual(response_checklist.status_code, 302)

        response_medicao = self.client.post(medicao_url, {f'quantidade_{contrato.itens.get().pk}': '2.00'})
        self.assertEqual(response_medicao.status_code, 302)

        response_pagamento = self.client.post(
            pagamento_url,
            {
                'nota_fiscal_fatura': SimpleUploadedFile('nf.pdf', b'%PDF-1.4 nf', content_type='application/pdf'),
                'atestado_realizacao': SimpleUploadedFile('atestado.pdf', b'%PDF-1.4 atestado', content_type='application/pdf'),
                'despacho_dof': SimpleUploadedFile('dof.pdf', b'%PDF-1.4 dof', content_type='application/pdf'),
                'valor_liberado_final': '100.00',
                'data_pagamento': '2026-01-31',
                'justificativa_divergencia': '',
            },
        )
        competencia.refresh_from_db()

        self.assertEqual(response_pagamento.status_code, 302)
        self.assertEqual(competencia.status, CompetenciaPagamentoV2.Status.PAGA)
        self.assertEqual(competencia.valor_medido, Decimal('100.00'))
        self.assertEqual(competencia.valor_liberado_sugerido, Decimal('100.00'))

    def test_fluxo_com_avaliacao_exige_justificativa_e_manifestacao(self):
        contrato = self.criar_contrato(prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos_v2:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', b'%PDF-1.4 doc', content_type='application/pdf')},
        )
        self.client.post(
            reverse('contratos_v2:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{contrato.itens.get().pk}': '2.00'},
        )
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()

        response_invalido = self.client.post(
            reverse('contratos_v2:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_{resposta.pk}': '1.00',
                f'justificativa_{resposta.pk}': '',
                'observacoes': '',
            },
        )
        self.assertContains(response_invalido, 'Informe a justificativa do fiscal')

        response_pendente = self.client.post(
            reverse('contratos_v2:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_{resposta.pk}': '1.00',
                f'justificativa_{resposta.pk}': 'Serviço parcialmente entregue.',
                'observacoes': 'Avaliação mensal',
            },
        )
        competencia.refresh_from_db()
        avaliacao.refresh_from_db()
        resposta.refresh_from_db()

        self.assertEqual(response_pendente.status_code, 302)
        self.assertEqual(competencia.status, CompetenciaPagamentoV2.Status.AVALIACAO_PENDENTE)
        self.assertIsNone(avaliacao.concluida_em)
        self.assertEqual(resposta.justificativa_fiscal, 'Serviço parcialmente entregue.')
        self.assertEqual(resposta.manifestacao_gestor_item, '')
        self.assertEqual(competencia.etapas[2], ('Avaliação', 'pending'))

        response_valido = self.client.post(
            reverse('contratos_v2:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_{resposta.pk}': '1.00',
                f'justificativa_{resposta.pk}': 'Serviço parcialmente entregue.',
                f'manifestacao_gestor_item_{resposta.pk}': 'Ciente da justificativa e da retenção neste item.',
                'observacoes': 'Avaliação mensal',
            },
        )
        competencia.refresh_from_db()
        avaliacao.refresh_from_db()
        resposta.refresh_from_db()

        self.assertEqual(response_valido.status_code, 302)
        self.assertEqual(competencia.status, CompetenciaPagamentoV2.Status.PAGAMENTO_PENDENTE)
        self.assertEqual(avaliacao.nota_final, Decimal('1.00'))
        self.assertEqual(avaliacao.percentual_liberacao_sugerido, Decimal('75.00'))
        self.assertEqual(competencia.valor_liberado_sugerido, Decimal('75.00'))
        self.assertEqual(resposta.manifestacao_gestor_item, 'Ciente da justificativa e da retenção neste item.')
        self.assertEqual(competencia.etapas[2], ('Avaliação', 'done'))

    def test_nao_permita_criar_formulario_de_avaliacao_apos_gerar_competencias(self):
        contrato = self.criar_contrato()
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(
            reverse('contratos_v2:avaliacao_form_create', args=[contrato.pk]),
            {
                'nome': 'Avaliação tardia',
                'descricao': 'Não deveria deixar',
                'ativo': 'on',
                'observacoes': '',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Não é permitido cadastrar avaliação de qualidade após a geração de competências.')
