# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Cobrir o CRUD principal e o fluxo mensal de checklist, competências, medição, avaliação e pagamento do Contratos V2.

from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from acls.models import Recurso, RegraAcesso
from contratos.models import EmpresaContratada

from .forms import (
    AvaliacaoCompetenciaV2Form,
    CompetenciaMedicaoLoteV2Form,
    CompetenciaPagamentoExecucaoV2Form,
    ContratoForm,
    EscalaNotaAvaliacaoForm,
    FaixaLiberacaoAvaliacaoForm,
    GrupoAvaliacaoForm,
    ItemAvaliacaoForm,
    validar_upload_pdf,
)
from .models import (
    ChecklistCompetenciaItem,
    ChecklistCompetenciaAnexo,
    ChecklistModeloItem,
    ChecklistModelo,
    ChecklistPadraoGlobal,
    ChecklistPadraoGlobalItem,
    CompetenciaAuditoriaEvento,
    CompetenciaPagamento,
    ContratoAuditoriaEvento,
    ContratoItem,
    Contrato,
    DocumentoImportanteContrato,
    EscalaNotaAvaliacao,
    EscalaNotaAvaliacaoPadraoGlobal,
    ExportacaoDocumentosCompetencia,
    FaixaLiberacaoAvaliacao,
    FaixaLiberacaoAvaliacaoPadraoGlobal,
    FormularioAvaliacao,
    FormularioAvaliacaoPadraoGlobal,
    GrupoAvaliacao,
    GrupoAvaliacaoPadraoGlobal,
    ItemAvaliacao,
    ItemAvaliacaoPadraoGlobal,
    PrazoMonitoramento,
)
from .services import (
    criar_avaliacao_shell_competencia_v2,
    usuario_pode_preencher_avaliacao_fiscal_v2,
    usuario_pode_preencher_avaliacao_gestor_v2,
)
from .views import CompetenciaAvaliacaoUpdateView, gerar_relatorio_avaliacao_competencia, gerar_ultima_folha_atestado


User = get_user_model()


def pdf_minimo_valido():
    """Entrega um PDF mínimo válido para cenários que realmente mesclam arquivos."""

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class ContratosTests(TestCase):
    """Valida a evolução do módulo Contratos V2 para o fluxo completo de competências."""

    def setUp(self):
        self.gestor = User.objects.create_user(username='gestor_v2', password='123', is_staff=True)
        self.criador = User.objects.create_user(username='criador_v2', password='123')
        self.fiscal_adm = User.objects.create_user(username='fadm_v2', password='123')
        self.fiscal_tec = User.objects.create_user(username='ftec_v2', password='123')
        self.operador = User.objects.create_user(username='operador_v2', password='123')
        self.recurso, _ = Recurso.objects.get_or_create(slug='contratos', defaults={'nome': 'Contratos V2'})
        regra = RegraAcesso.objects.create(recurso=self.recurso, nivel=RegraAcesso.NIVEL_MODIFICACAO)
        regra.usuarios.add(self.gestor, self.criador, self.fiscal_adm, self.fiscal_tec, self.operador)
        self.empresa = EmpresaContratada.objects.create(razao_social='Empresa V2', cnpj='11.111.111/0001-11')

    def criar_contrato(self, numero='001/2026', prazo=2, gestor=None, criado_por=None, data_inicio=None, situacao_forcada=''):
        return Contrato.objects.create(
            numero_contrato=numero,
            apelido='Contrato teste',
            objeto='Serviço continuado',
            data_inicio_vigencia=data_inicio or date(2026, 1, 1),
            prazo_inicial_meses=prazo,
            vigencia_maxima_meses=24,
            empresa_contratada=self.empresa,
            processo_sei_gestao_numero='SEI-G-2026-001',
            processo_sei_gestao_url='https://sei.exemplo/spi/gestao/1',
            processo_sei_execucao_numero='SEI-E-2026-001',
            processo_sei_execucao_url='https://sei.exemplo/spi/execucao/1',
            fiscal_administrativo=self.fiscal_adm,
            fiscal_tecnico=self.fiscal_tec,
            gestor_contrato=self.gestor if gestor is None else gestor,
            # Os testes de permissão precisam variar quem criou o contrato para cobrir a nova regra.
            criado_por=self.criador if criado_por is None else criado_por,
            situacao_forcada=situacao_forcada,
        )

    def criar_item_contrato(self, contrato, ordem=1, quantidade='10.00', unitario='100.00'):
        return ContratoItem.objects.create(
            contrato=contrato,
            ordem=ordem,
            descricao=f'Item {ordem}',
            quantidade=Decimal(quantidade),
            valor_unitario=Decimal(unitario),
        )

    def criar_checklist_ativo(self, contrato, nome='Checklist v1', titulo='FGTS'):
        checklist = ChecklistModelo.objects.create(
            contrato=contrato,
            nome=nome,
            descricao='Checklist da competência',
            ativo=True,
        )
        ChecklistModeloItem.objects.create(modelo=checklist, ordem=1, titulo=titulo, obrigatorio=True)
        return checklist

    def criar_formulario_avaliacao(self, contrato, nome='Avaliação 2026'):
        formulario = FormularioAvaliacao.objects.create(
            contrato=contrato,
            nome=nome,
            descricao='Modelo de qualidade',
            ativo=True,
        )
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=1, valor=Decimal('0.00'), legenda='Insatisfatório')
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=2, valor=Decimal('1.00'), legenda='Regular')
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=3, valor=Decimal('3.00'), legenda='Bom')
        FaixaLiberacaoAvaliacao.objects.create(
            formulario=formulario,
            ordem=1,
            nota_minima=Decimal('0.00'),
            nota_maxima=Decimal('1.99'),
            percentual_liberacao=Decimal('75.00'),
        )
        FaixaLiberacaoAvaliacao.objects.create(
            formulario=formulario,
            ordem=2,
            nota_minima=Decimal('2.00'),
            nota_maxima=Decimal('2.99'),
            percentual_liberacao=Decimal('90.00'),
        )
        FaixaLiberacaoAvaliacao.objects.create(
            formulario=formulario,
            ordem=3,
            nota_minima=Decimal('3.00'),
            percentual_liberacao=Decimal('100.00'),
        )
        grupo = GrupoAvaliacao.objects.create(formulario=formulario, ordem=1, nome='Desempenho')
        ItemAvaliacao.objects.create(grupo=grupo, ordem=1, descricao='Qualidade da entrega', peso_percentual=Decimal('100.00'))
        return formulario

    def criar_checklist_padrao_global(self, nome='Checklist padrão global', ativo=True):
        checklist = ChecklistPadraoGlobal.objects.create(
            nome=nome,
            descricao='Checklist padrão reutilizável',
            observacoes='Observações padrão',
            ativo=ativo,
            criado_por=self.gestor,
            atualizado_por=self.gestor,
        )
        ChecklistPadraoGlobalItem.objects.create(
            checklist_padrao=checklist,
            ordem=1,
            titulo='Documento padrão 1',
            descricao='Descrição do documento padrão 1',
            obrigatorio=True,
        )
        ChecklistPadraoGlobalItem.objects.create(
            checklist_padrao=checklist,
            ordem=2,
            titulo='Documento padrão 2',
            descricao='Descrição do documento padrão 2',
            obrigatorio=False,
        )
        return checklist

    def criar_formulario_padrao_global(self, nome='Avaliação padrão global', ativo=True):
        formulario = FormularioAvaliacaoPadraoGlobal.objects.create(
            nome=nome,
            descricao='Avaliação padrão reutilizável',
            observacoes='Observações padrão da avaliação',
            ativo=ativo,
            criado_por=self.gestor,
            atualizado_por=self.gestor,
        )
        EscalaNotaAvaliacaoPadraoGlobal.objects.create(
            formulario_padrao=formulario,
            ordem=1,
            valor=Decimal('1.00'),
            legenda='Insatisfatório',
        )
        FaixaLiberacaoAvaliacaoPadraoGlobal.objects.create(
            formulario_padrao=formulario,
            ordem=1,
            nota_minima=Decimal('1.00'),
            nota_maxima=Decimal('1.99'),
            percentual_liberacao=Decimal('50.00'),
        )
        grupo = GrupoAvaliacaoPadraoGlobal.objects.create(
            formulario_padrao=formulario,
            ordem=1,
            nome='Grupo padrão',
            descricao='Grupo institucional',
        )
        ItemAvaliacaoPadraoGlobal.objects.create(
            grupo_padrao=grupo,
            ordem=1,
            descricao='Item padrão de avaliação',
            peso_percentual=Decimal('100.00'),
            observacoes_padrao='Observação institucional',
        )
        return formulario

    def criar_documento_importante(self, contrato, nome='Documento base', usuario=None):
        return DocumentoImportanteContrato.objects.create(
            contrato=contrato,
            nome=nome,
            arquivo=SimpleUploadedFile('documento.pdf', pdf_minimo_valido(), content_type='application/pdf'),
            criado_por=usuario or self.criador,
            atualizado_por=usuario or self.criador,
        )

    def dados_contrato_post(self, numero='001/2026', apelido='Contrato web'):
        """Monta um payload mínimo válido para o formulário principal do contrato."""

        return {
            'numero_contrato': numero,
            'apelido': apelido,
            'objeto': 'Serviço continuado de teste',
            'data_inicio_vigencia': '2026-01-01',
            'prazo_inicial_meses': '2',
            'vigencia_maxima_meses': '24',
            'mes_reajuste': '01',
            'empresa_contratada': str(self.empresa.pk),
            'processo_sei_gestao_numero': 'SEI-G-2026-100',
            'processo_sei_gestao_url': 'https://sei.exemplo/spi/gestao/100',
            'processo_sei_execucao_numero': 'SEI-E-2026-100',
            'processo_sei_execucao_url': 'https://sei.exemplo/spi/execucao/100',
            'fiscal_administrativo': str(self.fiscal_adm.pk),
            'fiscal_tecnico': str(self.fiscal_tec.pk),
            'gestor_contrato': str(self.gestor.pk),
            'gestor_contrato_suplente': '',
            'fiscal_administrativo_suplente': '',
            'fiscal_tecnico_suplente': '',
            'situacao_forcada': '',
        }

    def test_formulario_gera_numero_incremental(self):
        self.criar_contrato(numero='001/2026')
        form = ContratoForm(
            data={
                'numero_contrato': '',
                'numero_contrato_incremental': 'on',
                'apelido': 'Contrato incremental',
                'objeto': 'Objeto incremental',
                'data_inicio_vigencia': '2026-06-01',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'processo_sei_gestao_numero': 'SEI-G-2026-010',
                'processo_sei_gestao_url': 'https://sei.exemplo/gestao/10',
                'processo_sei_execucao_numero': 'SEI-E-2026-010',
                'processo_sei_execucao_url': 'https://sei.exemplo/execucao/10',
                'fiscal_administrativo': str(self.fiscal_adm.pk),
                'fiscal_administrativo_suplente': '',
                'fiscal_tecnico': str(self.fiscal_tec.pk),
                'fiscal_tecnico_suplente': '',
                'gestor_contrato': str(self.gestor.pk),
                'gestor_contrato_suplente': '',
                'situacao_forcada': '',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['numero_contrato'], '002/2026')

    def test_formulario_aceita_responsaveis_em_branco_por_enquanto(self):
        form = ContratoForm(
            data={
                'numero_contrato': '010/2026',
                'apelido': 'Contrato sem responsáveis',
                'objeto': 'Objeto temporário',
                'data_inicio_vigencia': '2026-06-01',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'processo_sei_gestao_numero': 'SEI-G-2026-011',
                'processo_sei_gestao_url': 'https://sei.exemplo/gestao/11',
                'processo_sei_execucao_numero': 'SEI-E-2026-011',
                'processo_sei_execucao_url': 'https://sei.exemplo/execucao/11',
                'fiscal_administrativo': '',
                'fiscal_administrativo_suplente': '',
                'fiscal_tecnico': '',
                'fiscal_tecnico_suplente': '',
                'gestor_contrato': '',
                'gestor_contrato_suplente': '',
                'situacao_forcada': '',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_formulario_de_contrato_exige_processos_sei(self):
        form = ContratoForm(
            data={
                'numero_contrato': '012/2026',
                'apelido': 'Contrato sem SEI',
                'objeto': 'Objeto sem SEI',
                'data_inicio_vigencia': '2026-06-01',
                'prazo_inicial_meses': '12',
                'vigencia_maxima_meses': '24',
                'empresa_contratada': str(self.empresa.pk),
                'processo_sei_gestao_numero': '',
                'processo_sei_gestao_url': '',
                'processo_sei_execucao_numero': '',
                'processo_sei_execucao_url': '',
                'fiscal_administrativo': '',
                'fiscal_administrativo_suplente': '',
                'fiscal_tecnico': '',
                'fiscal_tecnico_suplente': '',
                'gestor_contrato': '',
                'gestor_contrato_suplente': '',
                'situacao_forcada': '',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('processo_sei_gestao_numero', form.errors)
        self.assertIn('processo_sei_gestao_url', form.errors)
        self.assertIn('processo_sei_execucao_numero', form.errors)
        self.assertIn('processo_sei_execucao_url', form.errors)

    def test_primeiro_checklist_do_contrato_nasce_ativo_automaticamente(self):
        contrato = self.criar_contrato(numero='014/2026')

        checklist = ChecklistModelo.objects.create(
            contrato=contrato,
            nome='Primeiro checklist',
            descricao='Checklist inicial do contrato',
            ativo=False,
        )

        checklist.refresh_from_db()
        self.assertTrue(checklist.ativo)
        self.assertEqual(contrato.checklist_ativo.pk, checklist.pk)

    def test_primeiro_formulario_de_avaliacao_nasce_ativo_automaticamente(self):
        contrato = self.criar_contrato(numero='015/2026')

        formulario = FormularioAvaliacao.objects.create(
            contrato=contrato,
            nome='Avaliação inicial',
            descricao='Primeiro formulário do contrato',
            ativo=False,
        )

        formulario.refresh_from_db()
        self.assertTrue(formulario.ativo)
        self.assertEqual(contrato.formulario_avaliacao_ativo.pk, formulario.pk)

    def test_primeiro_checklist_padrao_global_nasce_ativo_automaticamente(self):
        checklist = ChecklistPadraoGlobal.objects.create(
            nome='Checklist padrão inicial',
            descricao='Checklist padrão inicial',
            ativo=False,
        )

        checklist.refresh_from_db()
        self.assertTrue(checklist.ativo)

    def test_ativar_checklist_padrao_global_desativa_os_demais(self):
        primeiro = self.criar_checklist_padrao_global(nome='Padrão A', ativo=True)
        segundo = ChecklistPadraoGlobal.objects.create(
            nome='Padrão B',
            descricao='Segundo padrão',
            ativo=True,
        )

        primeiro.refresh_from_db()
        segundo.refresh_from_db()
        self.assertFalse(primeiro.ativo)
        self.assertTrue(segundo.ativo)

    def test_primeiro_formulario_padrao_global_nasce_ativo_automaticamente(self):
        formulario = FormularioAvaliacaoPadraoGlobal.objects.create(
            nome='Avaliação padrão inicial',
            descricao='Primeiro formulário padrão',
            ativo=False,
        )

        formulario.refresh_from_db()
        self.assertTrue(formulario.ativo)

    def test_ativar_formulario_padrao_global_desativa_os_demais(self):
        primeiro = self.criar_formulario_padrao_global(nome='Avaliação padrão A', ativo=True)
        segundo = FormularioAvaliacaoPadraoGlobal.objects.create(
            nome='Avaliação padrão B',
            descricao='Segundo formulário padrão',
            ativo=True,
        )

        primeiro.refresh_from_db()
        segundo.refresh_from_db()
        self.assertFalse(primeiro.ativo)
        self.assertTrue(segundo.ativo)

    def test_lista_renderiza_atalho_global_apenas_para_gestor_admin(self):
        self.criar_checklist_padrao_global()
        self.criar_formulario_padrao_global()

        self.client.force_login(self.gestor)
        response_gestor = self.client.get(reverse('contratos:contrato_list'))
        self.assertContains(response_gestor, 'Checklists Padrão')
        self.assertContains(response_gestor, 'Avaliações Padrão')
        self.assertNotContains(response_gestor, 'Checklists Padrão Globais')
        self.client.logout()

        self.client.login(username='operador_v2', password='123')
        response_operador = self.client.get(reverse('contratos:contrato_list'))
        self.assertNotContains(response_operador, 'Checklists Padrão')
        self.assertNotContains(response_operador, 'Avaliações Padrão')

    def test_lista_renderiza_dashboard_operacional_da_carteira(self):
        hoje = timezone.localdate()
        contrato_vigente = self.criar_contrato(
            numero='201/2026',
            prazo=12,
            data_inicio=hoje - timedelta(days=120),
        )
        self.criar_item_contrato(contrato_vigente, quantidade='10.00', unitario='100.00')
        self.criar_checklist_ativo(contrato_vigente)
        contrato_vigente.gerar_competencias()
        competencia_atrasada = contrato_vigente.competencias.first()
        competencia_atrasada.monitoramento_etapa = 'Aguardando conclusão do pagamento'
        competencia_atrasada.monitoramento_inicio = hoje - timedelta(days=20)
        competencia_atrasada.monitoramento_limite = hoje - timedelta(days=3)
        competencia_atrasada.status = CompetenciaPagamento.Status.OB_PENDENTE
        competencia_atrasada.save(update_fields=['monitoramento_etapa', 'monitoramento_inicio', 'monitoramento_limite', 'status', 'atualizado_em'])
        prazo_critico = PrazoMonitoramento.objects.create(
            contrato=contrato_vigente,
            nome='Certidão crítica',
            data_inicio=hoje - timedelta(days=20),
            data_limite=hoje - timedelta(days=1),
        )

        contrato_30 = self.criar_contrato(
            numero='202/2026',
            prazo=1,
            data_inicio=hoje - timedelta(days=5),
        )
        self.criar_item_contrato(contrato_30, quantidade='1.00', unitario='50.00')

        contrato_60 = self.criar_contrato(
            numero='203/2026',
            prazo=2,
            data_inicio=hoje - timedelta(days=2),
        )
        self.criar_item_contrato(contrato_60, quantidade='1.00', unitario='60.00')

        contrato_90 = self.criar_contrato(
            numero='204/2026',
            prazo=3,
            data_inicio=hoje - timedelta(days=2),
        )
        self.criar_item_contrato(contrato_90, quantidade='1.00', unitario='70.00')

        contrato_encerrado = self.criar_contrato(
            numero='205/2026',
            prazo=1,
            data_inicio=hoje - timedelta(days=90),
            situacao_forcada=Contrato.Situacao.ENCERRADO,
        )
        self.criar_item_contrato(contrato_encerrado, quantidade='1.00', unitario='80.00')

        self.client.force_login(self.gestor)
        response = self.client.get(reverse('contratos:contrato_list'))

        self.assertContains(response, 'Contratos vigentes')
        self.assertContains(response, 'Contratos com atenção operacional')
        self.assertEqual(response.context['dashboard_resumo']['vigentes'], 4)
        self.assertEqual(response.context['dashboard_resumo']['vence_ate_30_dias'], 1)
        self.assertEqual(response.context['dashboard_resumo']['vence_31_60_dias'], 1)
        self.assertEqual(response.context['dashboard_resumo']['vence_61_90_dias'], 1)
        self.assertEqual(response.context['dashboard_resumo']['competencias_atrasadas'], 1)
        self.assertEqual(response.context['dashboard_resumo']['pagamentos_pendentes'], 1)
        self.assertEqual(response.context['dashboard_resumo']['prazos_criticos'], 1)
        self.assertEqual(response.context['dashboard_contratos_operacionais'][0].pk, contrato_vigente.pk)
        self.assertEqual(response.context['dashboard_contratos_operacionais'][0].dashboard_prazos_criticos, 1)
        self.assertEqual(prazo_critico.contrato_id, contrato_vigente.pk)

    def test_lista_dashboard_respeita_busca_atual(self):
        hoje = timezone.localdate()
        contrato_alvo = self.criar_contrato(
            numero='210/2026',
            prazo=1,
            data_inicio=hoje - timedelta(days=5),
        )
        self.criar_item_contrato(contrato_alvo, quantidade='1.00', unitario='90.00')
        contrato_outro = self.criar_contrato(
            numero='211/2026',
            prazo=1,
            data_inicio=hoje - timedelta(days=5),
        )
        self.criar_item_contrato(contrato_outro, quantidade='1.00', unitario='120.00')

        self.client.force_login(self.gestor)
        response = self.client.get(reverse('contratos:contrato_list'), {'q': '210/2026'})

        self.assertContains(response, '210/2026')
        self.assertNotContains(response, '211/2026')
        self.assertEqual(response.context['dashboard_resumo']['vigentes'], 1)
        self.assertNotContains(response, 'Saldo financeiro da carteira')
        self.assertNotIn('saldo_total', response.context['dashboard_resumo'])

    def test_lista_de_checklists_padrao_exibe_colunas_e_link_para_tela_propria(self):
        checklist = self.criar_checklist_padrao_global(nome='Padrão institucional')
        self.client.force_login(self.gestor)

        response = self.client.get(reverse('contratos:checklist_padrao_list'))

        self.assertContains(response, 'Novo Checklist Padrão')
        self.assertContains(response, 'Último usuário que alterou')
        self.assertContains(response, 'Data da última alteração')
        self.assertContains(response, checklist.nome)
        self.assertContains(response, reverse('contratos:checklist_padrao_detail', args=[checklist.pk]))
        self.assertContains(response, self.gestor.username)

    def test_detalhe_do_checklist_padrao_exibe_itens_em_tela_propria(self):
        checklist = self.criar_checklist_padrao_global(nome='Padrão detalhado')
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos:checklist_padrao_detail', args=[checklist.pk]))

        self.assertContains(response, 'Itens do Checklist')
        self.assertContains(response, 'Documento padrão 1')
        self.assertContains(response, 'Novo item')

    def test_lista_de_formularios_padrao_exibe_colunas_e_link_para_tela_propria(self):
        formulario = self.criar_formulario_padrao_global(nome='Avaliação institucional')
        self.client.force_login(self.gestor)

        response = self.client.get(reverse('contratos:avaliacao_padrao_list'))

        self.assertContains(response, 'Novo Formulário Padrão')
        self.assertContains(response, 'Último usuário que alterou')
        self.assertContains(response, 'Data da última alteração')
        self.assertContains(response, formulario.nome)
        self.assertContains(response, reverse('contratos:avaliacao_padrao_detail', args=[formulario.pk]))
        self.assertContains(response, self.gestor.username)

    def test_detalhe_do_formulario_padrao_exibe_blocos_em_tela_propria(self):
        formulario = self.criar_formulario_padrao_global(nome='Avaliação detalhada')
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos:avaliacao_padrao_detail', args=[formulario.pk]))

        self.assertContains(response, 'Escala')
        self.assertContains(response, 'Faixas de liberação')
        self.assertContains(response, 'Grupos e itens')
        self.assertContains(response, 'Item padrão de avaliação')

    def test_operador_sem_perfil_gestor_nao_pode_manter_checklist_padrao_global(self):
        self.client.login(username='operador_v2', password='123')

        response = self.client.post(
            reverse('contratos:checklist_padrao_create'),
            {
                'nome': 'Padrão indevido',
                'descricao': 'Não deveria ser criado',
                'observacoes': '',
                'ativo': 'on',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('contratos:contrato_list'))
        self.assertContains(response, 'Somente gestores e administradores do sistema podem manter checklists padrão globais.')
        self.assertFalse(ChecklistPadraoGlobal.objects.filter(nome='Padrão indevido').exists())

    def test_operador_sem_perfil_gestor_nao_pode_manter_formulario_padrao_global(self):
        self.client.login(username='operador_v2', password='123')

        response = self.client.post(
            reverse('contratos:avaliacao_padrao_create'),
            {
                'nome': 'Avaliação indevida',
                'descricao': 'Não deveria ser criada',
                'observacoes': '',
                'ativo': 'on',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('contratos:contrato_list'))
        self.assertContains(response, 'Somente gestores e administradores do sistema podem manter formulários de avaliação padrão globais.')
        self.assertFalse(FormularioAvaliacaoPadraoGlobal.objects.filter(nome='Avaliação indevida').exists())

    def test_detalhe_do_contrato_exibe_secao_de_checklist_padrao_antes_das_competencias(self):
        contrato = self.criar_contrato(numero='015A/2026')
        checklist_padrao = self.criar_checklist_padrao_global(nome='Padrão institucional')
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Checklist Padrão')
        self.assertContains(response, checklist_padrao.nome)
        self.assertContains(response, 'Carregar Checklist')

    def test_detalhe_do_contrato_exibe_secao_de_formulario_padrao_antes_das_competencias(self):
        contrato = self.criar_contrato(numero='015A1/2026')
        formulario_padrao = self.criar_formulario_padrao_global(nome='Avaliação institucional')
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Formulário de Avaliação Padrão')
        self.assertContains(response, formulario_padrao.nome)
        self.assertContains(response, 'Carregar Formulário')

    def test_carregar_checklist_padrao_clona_itens_e_ativa_nova_versao_do_contrato(self):
        contrato = self.criar_contrato(numero='015B/2026')
        checklist_anterior = self.criar_checklist_ativo(contrato, nome='Checklist manual', titulo='Documento manual')
        checklist_padrao = self.criar_checklist_padrao_global(nome='Padrão institucional')
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(
            reverse('contratos:checklist_padrao_carregar', args=[contrato.pk]),
            {'checklist_padrao_id': str(checklist_padrao.pk)},
        )

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        checklist_anterior.refresh_from_db()
        nova_versao = contrato.checklist_modelos.exclude(pk=checklist_anterior.pk).get()

        self.assertFalse(checklist_anterior.ativo)
        self.assertTrue(nova_versao.ativo)
        self.assertEqual(nova_versao.nome, 'Padrão institucional (Padrão)')
        self.assertEqual(
            list(nova_versao.itens.values_list('titulo', 'ordem', 'obrigatorio')),
            [
                ('Documento padrão 1', 1, True),
                ('Documento padrão 2', 2, False),
            ],
        )

    def test_carregar_formulario_padrao_clona_blocos_e_ativa_nova_versao_do_contrato(self):
        contrato = self.criar_contrato(numero='015B1/2026')
        formulario_anterior = self.criar_formulario_avaliacao(contrato, nome='Avaliação manual')
        formulario_padrao = self.criar_formulario_padrao_global(nome='Avaliação institucional')
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(
            reverse('contratos:avaliacao_padrao_carregar', args=[contrato.pk]),
            {'formulario_padrao_id': str(formulario_padrao.pk)},
        )

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        formulario_anterior.refresh_from_db()
        nova_versao = contrato.formularios_avaliacao.exclude(pk=formulario_anterior.pk).get()

        self.assertFalse(formulario_anterior.ativo)
        self.assertTrue(nova_versao.ativo)
        self.assertEqual(nova_versao.nome, 'Avaliação institucional (Padrão)')
        self.assertEqual(list(nova_versao.escalas.values_list('valor', 'legenda')), [(Decimal('1.00'), 'Insatisfatório')])
        self.assertEqual(
            list(nova_versao.faixas_liberacao.values_list('nota_minima', 'nota_maxima', 'percentual_liberacao')),
            [(Decimal('1.00'), Decimal('1.99'), Decimal('50.00'))],
        )
        grupo = nova_versao.grupos.get()
        self.assertEqual(grupo.nome, 'Grupo padrão')
        self.assertEqual(
            list(grupo.itens.values_list('descricao', 'peso_percentual', 'observacoes_padrao')),
            [('Item padrão de avaliação', Decimal('100.00'), 'Observação institucional')],
        )

    def test_alterar_checklist_padrao_global_nao_muda_copia_ja_carregada_no_contrato(self):
        contrato = self.criar_contrato(numero='015C/2026')
        checklist_padrao = self.criar_checklist_padrao_global(nome='Padrão estável')
        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos:checklist_padrao_carregar', args=[contrato.pk]),
            {'checklist_padrao_id': str(checklist_padrao.pk)},
        )
        checklist_clonado = contrato.checklist_modelos.get()
        item_padrao = checklist_padrao.itens.get(ordem=1)

        item_padrao.titulo = 'Documento padrão atualizado'
        item_padrao.save(update_fields=['titulo', 'atualizado_em'])
        checklist_clonado.refresh_from_db()

        self.assertEqual(checklist_clonado.itens.get(ordem=1).titulo, 'Documento padrão 1')

    def test_nao_permite_carregar_checklist_padrao_em_contrato_com_competencias(self):
        contrato = self.criar_contrato(numero='015D/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        checklist_padrao = self.criar_checklist_padrao_global(nome='Padrão bloqueado')
        quantidade_antes = contrato.checklist_modelos.count()
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(
            reverse('contratos:checklist_padrao_carregar', args=[contrato.pk]),
            {'checklist_padrao_id': str(checklist_padrao.pk)},
            follow=True,
        )

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]))
        self.assertContains(response, 'Ação bloqueada: Este contrato já possui competências geradas.')
        self.assertEqual(contrato.checklist_modelos.count(), quantidade_antes)

    def test_detalhe_exibe_botao_de_reset_da_competencia_apenas_para_gestor(self):
        contrato = self.criar_contrato(numero='015D1/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.first()

        self.client.login(username='gestor_v2', password='123')
        response_gestor = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))
        self.assertContains(response_gestor, 'Resetar competência')
        self.assertContains(response_gestor, reverse('contratos:competencia_reset', args=[competencia.pk]))
        self.client.logout()

        self.client.login(username='operador_v2', password='123')
        response_operador = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))
        self.assertNotContains(response_operador, 'Resetar competência')

    def test_reset_da_competencia_limpa_fluxo_operacional_e_registra_auditoria(self):
        contrato = self.criar_contrato(numero='015D2/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.first()
        item_checklist = competencia.checklist_itens.first()

        ChecklistCompetenciaAnexo.objects.create(
            item=item_checklist,
            arquivo=SimpleUploadedFile('checklist.pdf', pdf_minimo_valido(), content_type='application/pdf'),
            nome_exibicao='checklist.pdf',
        )
        ChecklistCompetenciaItem.objects.create(
            competencia=competencia,
            ordem=99,
            titulo='Documento nota adicional',
            categoria=ChecklistCompetenciaItem.Categoria.NOTA_ADICIONAL,
            obrigatorio=True,
        )
        competencia.medicoes.create(
            item_contrato=contrato.itens.first(),
            quantidade=Decimal('2.00'),
            valor_unitario_aplicado=Decimal('100.00'),
            valor_subtotal=Decimal('200.00'),
        )
        avaliacao = competencia.avaliacao_qualidade_segura
        resposta = avaliacao.itens.first()
        resposta.nota_fiscal_valor = Decimal('1.00')
        resposta.nota_gestor_valor = Decimal('1.00')
        resposta.nota_valor = Decimal('1.00')
        resposta.justificativa_fiscal = 'Justificativa'
        resposta.manifestacao_gestor_item = 'Manifestação'
        resposta.save()
        avaliacao.observacoes = 'Avaliação preenchida'
        avaliacao.concluida_em = timezone.now()
        avaliacao.save(update_fields=['observacoes', 'concluida_em', 'atualizado_em'])
        competencia.status = CompetenciaPagamento.Status.PAGA
        competencia.medicao_concluida_em = timezone.now()
        competencia.checklist_concluido_em = timezone.now()
        competencia.download_realizado_em = timezone.now()
        competencia.data_pagamento = timezone.localdate()
        competencia.numero_nota_fiscal = '123'
        competencia.valor_nota_fiscal = Decimal('200.00')
        competencia.nota_adicional_nao_consta = True
        competencia.observacoes_medicao = 'Observação final'
        competencia.nota_fiscal_fatura = SimpleUploadedFile('nf.pdf', pdf_minimo_valido(), content_type='application/pdf')
        competencia.avaliacao_assinada = SimpleUploadedFile('avaliacao.pdf', pdf_minimo_valido(), content_type='application/pdf')
        competencia.ordem_bancaria_arquivo = SimpleUploadedFile('ob.pdf', pdf_minimo_valido(), content_type='application/pdf')
        competencia.save()

        self.client.login(username='gestor_v2', password='123')
        response = self.client.post(reverse('contratos:competencia_reset', args=[competencia.pk]))

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        competencia.refresh_from_db()
        resposta.refresh_from_db()
        item_checklist.refresh_from_db()

        self.assertEqual(competencia.status, CompetenciaPagamento.Status.MEDICAO_PENDENTE)
        self.assertEqual(competencia.valor_medido, Decimal('0.00'))
        self.assertEqual(competencia.valor_liberado_sugerido, Decimal('0.00'))
        self.assertIsNone(competencia.medicao_concluida_em)
        self.assertIsNone(competencia.checklist_concluido_em)
        self.assertIsNone(competencia.download_realizado_em)
        self.assertIsNone(competencia.data_pagamento)
        self.assertFalse(bool(competencia.nota_fiscal_fatura))
        self.assertFalse(bool(competencia.avaliacao_assinada))
        self.assertFalse(bool(competencia.ordem_bancaria_arquivo))
        self.assertEqual(competencia.medicoes.count(), 0)
        self.assertEqual(competencia.checklist_itens.filter(categoria=ChecklistCompetenciaItem.Categoria.NOTA_ADICIONAL).count(), 0)
        self.assertFalse(item_checklist.concluido)
        self.assertIsNone(item_checklist.validado_em)
        self.assertIsNone(resposta.nota_fiscal_valor)
        self.assertIsNone(resposta.nota_gestor_valor)
        self.assertEqual(resposta.justificativa_fiscal, '')
        self.assertEqual(resposta.manifestacao_gestor_item, '')
        self.assertTrue(
            competencia.auditoria_eventos.filter(tipo_evento=CompetenciaAuditoriaEvento.TipoEvento.RESET_EXECUTADO).exists()
        )

    def test_exclusao_de_contrato_remove_dependencias_mesmo_com_competencias_e_avaliacoes(self):
        contrato = self.criar_contrato(numero='015E/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(reverse('contratos:contrato_delete', args=[contrato.pk]))

        self.assertRedirects(response, reverse('contratos:contrato_list'), fetch_redirect_response=False)
        self.assertFalse(Contrato.objects.filter(pk=contrato.pk).exists())
        self.assertFalse(FormularioAvaliacao.objects.filter(contrato_id=contrato.pk).exists())
        self.assertFalse(CompetenciaPagamento.objects.filter(contrato_id=contrato.pk).exists())

    def test_prazo_monitoramento_usa_data_inicio_no_percentual(self):
        contrato = self.criar_contrato()
        hoje = timezone.localdate()
        prazo = PrazoMonitoramento.objects.create(
            contrato=contrato,
            nome='Reajuste anual',
            data_inicio=hoje - timedelta(days=10),
            data_limite=hoje,
        )
        prazo.criado_em = datetime.combine(hoje - timedelta(days=1), datetime.min.time(), tzinfo=dt_timezone.utc)
        self.assertEqual(prazo.percentual_decorrido, 100)

    def test_prazo_monitoramento_legado_usa_criado_em_sem_data_inicio(self):
        contrato = self.criar_contrato()
        hoje = timezone.localdate()
        prazo = PrazoMonitoramento.objects.create(
            contrato=contrato,
            nome='Certidão',
            data_limite=hoje + timedelta(days=6),
        )
        prazo.criado_em = datetime.combine(hoje, datetime.min.time(), tzinfo=dt_timezone.utc)
        self.assertEqual(prazo.percentual_decorrido, 0)

    def test_formulario_de_escala_nao_expoe_ordem(self):
        form = EscalaNotaAvaliacaoForm()

        self.assertNotIn('ordem', form.fields)

    def test_formulario_de_faixa_nao_expoe_ordem(self):
        form = FaixaLiberacaoAvaliacaoForm()

        self.assertNotIn('ordem', form.fields)

    def test_formulario_de_grupo_nao_expoe_ordem_nem_peso(self):
        form = GrupoAvaliacaoForm()

        self.assertNotIn('ordem', form.fields)
        self.assertNotIn('peso_percentual', form.fields)

    def test_formulario_de_item_nao_expoe_ordem(self):
        form = ItemAvaliacaoForm()

        self.assertNotIn('ordem', form.fields)

    def test_formulario_de_avaliacao_inicia_notas_em_branco_sem_herdar_do_outro_papel(self):
        contrato = self.criar_contrato(numero='011/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        formulario = self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()

        form_inicial = AvaliacaoCompetenciaV2Form(
            avaliacao=avaliacao,
            pode_preencher_fiscal=True,
            pode_preencher_gestor=True,
        )
        self.assertIsNone(form_inicial.fields[f'nota_fiscal_{resposta.pk}'].initial)
        self.assertIsNone(form_inicial.fields[f'nota_gestor_{resposta.pk}'].initial)

        resposta.nota_fiscal_valor = Decimal('1.00')
        resposta.nota_valor = Decimal('1.00')
        resposta.save(update_fields=['nota_fiscal_valor', 'nota_valor', 'atualizado_em'])

        form_gestor = AvaliacaoCompetenciaV2Form(
            avaliacao=avaliacao,
            pode_preencher_fiscal=False,
            pode_preencher_gestor=True,
        )
        self.assertIsNone(form_gestor.fields[f'nota_gestor_{resposta.pk}'].initial)

    def test_avaliacao_pode_ser_salva_sem_pdf_assinado_e_fica_disponivel_para_download(self):
        contrato = self.criar_contrato(numero='011/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.save(update_fields=['medicao_concluida_em', 'atualizado_em'])
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()

        form = AvaliacaoCompetenciaV2Form(
            data={
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Serviço parcialmente entregue.',
                f'nota_gestor_{resposta.pk}': '1.00',
                f'manifestacao_gestor_item_{resposta.pk}': 'Ciente da justificativa e da retenção neste item.',
                'observacoes': 'Avaliação mensal',
            },
            avaliacao=avaliacao,
            pode_preencher_fiscal=True,
            pode_preencher_gestor=True,
        )
        self.assertTrue(form.is_valid(), form.errors)

        resposta.nota_fiscal_valor = Decimal('1.00')
        resposta.justificativa_fiscal = 'Serviço parcialmente entregue.'
        resposta.nota_gestor_valor = Decimal('1.00')
        resposta.manifestacao_gestor_item = 'Ciente da justificativa e da retenção neste item.'
        resposta.nota_valor = Decimal('1.00')
        resposta.save(
            update_fields=[
                'nota_fiscal_valor',
                'justificativa_fiscal',
                'nota_gestor_valor',
                'manifestacao_gestor_item',
                'nota_valor',
                'atualizado_em',
            ]
        )
        avaliacao.observacoes = 'Avaliação mensal'
        avaliacao.save(update_fields=['observacoes', 'atualizado_em'])

        competencia.refresh_from_db()
        avaliacao.refresh_from_db()
        self.assertIsNone(avaliacao.concluida_em)
        self.assertFalse(bool(competencia.avaliacao_assinada))
        view = CompetenciaAvaliacaoUpdateView()
        view.avaliacao = avaliacao
        self.assertTrue(view._avaliacao_possui_conteudo_salvo())

    def test_download_da_avaliacao_gera_pdf_com_conteudo_salvo(self):
        contrato = self.criar_contrato(numero='012/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()
        resposta.nota_fiscal_valor = Decimal('1.00')
        resposta.justificativa_fiscal = 'Serviço parcialmente entregue.'
        resposta.nota_gestor_valor = Decimal('1.00')
        resposta.manifestacao_gestor_item = 'Ciente da justificativa e da retenção neste item.'
        resposta.nota_valor = Decimal('1.00')
        resposta.save(
            update_fields=[
                'nota_fiscal_valor',
                'justificativa_fiscal',
                'nota_gestor_valor',
                'manifestacao_gestor_item',
                'nota_valor',
                'atualizado_em',
            ]
        )
        avaliacao.observacoes = 'Avaliação mensal'
        avaliacao.save(update_fields=['observacoes', 'atualizado_em'])

        self.client.login(username='gestor_v2', password='123')

        def fake_converter_docx_para_pdf(docx_file, output_dir):
            pdf_path = Path(output_dir) / f'{Path(docx_file).stem}.pdf'
            pdf_path.write_bytes(pdf_minimo_valido())
            return pdf_path

        with patch('contratos.views._converter_docx_para_pdf', side_effect=fake_converter_docx_para_pdf):
            response = self.client.get(reverse('contratos:competencia_avaliacao_download', args=[competencia.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('avaliacao_competencia_01_2026.pdf', response['Content-Disposition'])

    def test_atestado_monta_tabelas_de_acompanhamento_e_checklist(self):
        contrato = self.criar_contrato(numero='014/2026', prazo=12)
        self.criar_item_contrato(contrato)
        competencia = CompetenciaPagamento.objects.create(
            contrato=contrato,
            periodo_inicio=date(2026, 3, 1),
            periodo_fim=date(2026, 3, 31),
            status=CompetenciaPagamento.Status.OB_PENDENTE,
            data_aceite_definitivo=date(2026, 4, 14),
            prazo_pagamento_dias=12,
            numero_nota_fiscal='878',
            valor_nota_fiscal=Decimal('1000.00'),
            valor_liberado_final=Decimal('900.00'),
        )
        responsavel = contrato.empresa_contratada.responsaveis.create(
            nome='Gabriel Santos',
            telefone='11-963277678',
            email='gabriel@example.com',
            ativo=True,
        )

        doc = gerar_ultima_folha_atestado('/root/aplicacoesspi/docs/papel-timbrado-spi.docx', contrato, competencia)
        texto_tabelas = '\n'.join(celula.text for tabela in doc.tables for linha in tabela.rows for celula in linha.cells)

        self.assertIn('ACOMPANHAMENTO DE PAGAMENTO', texto_tabelas)
        self.assertIn('CHECKLIST DE VERIFICAÇÃO', texto_tabelas)
        self.assertIn(contrato.empresa_contratada.razao_social, texto_tabelas)
        self.assertIn(contrato.processo_sei_gestao_numero, texto_tabelas)
        self.assertIn(contrato.processo_sei_execucao_numero, texto_tabelas)
        self.assertIn('14/04/2026', texto_tabelas)
        self.assertIn('14/05/2026', texto_tabelas)
        self.assertIn('878', texto_tabelas)
        self.assertIn(responsavel.nome, texto_tabelas)
        self.assertIn('11-963277678 | gabriel@example.com', texto_tabelas)
        self.assertIn('VIGÊNCIA DO CONTRATO', texto_tabelas)
        self.assertIn('31/12/2026', texto_tabelas)

    def test_avaliacao_com_tres_itens_calcula_media_ponderada_no_total(self):
        contrato = self.criar_contrato(numero='013/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        formulario = FormularioAvaliacao.objects.create(
            contrato=contrato,
            nome='Avaliação do Novo Fluxo',
            descricao='Modelo com três itens',
            ativo=True,
        )
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=1, valor=Decimal('0.00'), legenda='Insatisfatório')
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=2, valor=Decimal('1.00'), legenda='Regular')
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=3, valor=Decimal('3.00'), legenda='Bom')
        FaixaLiberacaoAvaliacao.objects.create(
            formulario=formulario,
            ordem=1,
            nota_minima=Decimal('0.00'),
            nota_maxima=Decimal('4.99'),
            percentual_liberacao=Decimal('75.00'),
        )
        FaixaLiberacaoAvaliacao.objects.create(
            formulario=formulario,
            ordem=2,
            nota_minima=Decimal('5.00'),
            nota_maxima=Decimal('6.74'),
            percentual_liberacao=Decimal('75.00'),
        )
        FaixaLiberacaoAvaliacao.objects.create(
            formulario=formulario,
            ordem=3,
            nota_minima=Decimal('6.75'),
            nota_maxima=Decimal('9.00'),
            percentual_liberacao=Decimal('100.00'),
        )
        grupo = GrupoAvaliacao.objects.create(formulario=formulario, ordem=1, nome='Grupo A')
        ItemAvaliacao.objects.create(grupo=grupo, ordem=1, descricao='Item 1', peso_percentual=Decimal('30.00'))
        ItemAvaliacao.objects.create(grupo=grupo, ordem=2, descricao='Item 2', peso_percentual=Decimal('30.00'))
        ItemAvaliacao.objects.create(grupo=grupo, ordem=3, descricao='Item 3', peso_percentual=Decimal('40.00'))

        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        avaliacao = competencia.avaliacao_qualidade

        for resposta in avaliacao.itens.all():
            resposta.nota_fiscal_valor = Decimal('3.00')
            resposta.nota_gestor_valor = Decimal('3.00')
            resposta.nota_valor = Decimal('3.00')
            resposta.save(
                update_fields=[
                    'nota_fiscal_valor',
                    'nota_gestor_valor',
                    'nota_valor',
                    'atualizado_em',
                ]
            )

        from .services import recalcular_avaliacao_v2
        recalcular_avaliacao_v2(avaliacao)
        avaliacao.refresh_from_db()

        self.assertEqual(avaliacao.nota_final, Decimal('3.00'))
        self.assertEqual(avaliacao.percentual_liberacao_sugerido, Decimal('75.00'))

        doc = gerar_relatorio_avaliacao_competencia('/root/aplicacoesspi/docs/papel-timbrado-spi.docx', contrato, competencia)
        texto = '\n'.join(paragrafo.text for paragrafo in doc.paragraphs)
        self.assertIn('Nota final: 3.00', texto)

    def test_relatorio_da_avaliacao_recalcula_total_antes_do_download(self):
        contrato = self.criar_contrato(numero='015/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        formulario = FormularioAvaliacao.objects.create(
            contrato=contrato,
            nome='Avaliação do Novo Fluxo',
            descricao='Modelo com três itens',
            ativo=True,
        )
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=1, valor=Decimal('0.00'), legenda='Insatisfatório')
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=2, valor=Decimal('1.00'), legenda='Regular')
        EscalaNotaAvaliacao.objects.create(formulario=formulario, ordem=3, valor=Decimal('3.00'), legenda='Bom')
        FaixaLiberacaoAvaliacao.objects.create(formulario=formulario, ordem=1, nota_minima=Decimal('0.00'), nota_maxima=Decimal('4.99'), percentual_liberacao=Decimal('75.00'))
        FaixaLiberacaoAvaliacao.objects.create(formulario=formulario, ordem=2, nota_minima=Decimal('5.00'), nota_maxima=Decimal('6.74'), percentual_liberacao=Decimal('75.00'))
        FaixaLiberacaoAvaliacao.objects.create(formulario=formulario, ordem=3, nota_minima=Decimal('6.75'), nota_maxima=Decimal('9.00'), percentual_liberacao=Decimal('100.00'))
        grupo = GrupoAvaliacao.objects.create(formulario=formulario, ordem=1, nome='Grupo A')
        ItemAvaliacao.objects.create(grupo=grupo, ordem=1, descricao='Item 1', peso_percentual=Decimal('30.00'))
        ItemAvaliacao.objects.create(grupo=grupo, ordem=2, descricao='Item 2', peso_percentual=Decimal('30.00'))
        ItemAvaliacao.objects.create(grupo=grupo, ordem=3, descricao='Item 3', peso_percentual=Decimal('40.00'))

        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        avaliacao = competencia.avaliacao_qualidade
        notas_por_item = [Decimal('1.00'), Decimal('1.00'), Decimal('3.00')]
        for resposta, nota in zip(avaliacao.itens.order_by('grupo_ordem', 'item_ordem', 'id'), notas_por_item):
            resposta.nota_fiscal_valor = nota
            resposta.nota_valor = nota
            resposta.save(update_fields=['nota_fiscal_valor', 'nota_valor', 'atualizado_em'])
        avaliacao.nota_final = Decimal('5.00')
        avaliacao.percentual_liberacao_sugerido = Decimal('75.00')
        avaliacao.save(update_fields=['nota_final', 'percentual_liberacao_sugerido', 'atualizado_em'])

        doc = gerar_relatorio_avaliacao_competencia('/root/aplicacoesspi/docs/papel-timbrado-spi.docx', contrato, competencia)
        avaliacao.refresh_from_db()
        texto = '\n'.join(paragrafo.text for paragrafo in doc.paragraphs)

        self.assertEqual(avaliacao.nota_final, Decimal('1.80'))
        self.assertIn('Nota final: 1.80', texto)

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

    def test_formulario_de_pagamento_calcula_valor_liquido_com_retencoes(self):
        contrato = self.criar_contrato(numero='015/2026', prazo=1)
        competencia = contrato.competencias.model.objects.create(
            contrato=contrato,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
            status=CompetenciaPagamento.Status.PAGAMENTO_PENDENTE,
            valor_liberado_sugerido=Decimal('1000.00'),
        )
        form = CompetenciaPagamentoExecucaoV2Form(
            competencia=competencia,
            data={
                'valor_nota_fiscal': '1000.00',
                'retencao_ir': '100.00',
                'retencao_inss': '50.00',
                'retencao_iss': '25.00',
                'retencao_pis_pasep': '10.00',
                'retencao_cofins': '15.00',
                'valor_liberado_final': '0.00',
                'gestor_pagamento': str(self.gestor.pk),
                'gestor_pagamento_em_exercicio': 'on',
                'coordenadora_pagamento': str(self.operador.pk),
                'coordenadora_em_exercicio': 'on',
                'diretora_pagamento': str(self.fiscal_adm.pk),
                'diretora_em_exercicio': '',
                'subsecretario_pagamento': str(self.fiscal_tec.pk),
                'subsecretario_em_exercicio': '',
                'data_pagamento': '2026-01-31',
                'justificativa_divergencia': 'Pagamento líquido após retenções.',
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['valor_liberado_final'], Decimal('800.00'))
        self.assertTrue(form.cleaned_data['gestor_pagamento_em_exercicio'])

    def test_formulario_de_pagamento_preenche_gestor_do_contrato_por_padrao(self):
        contrato = self.criar_contrato(numero='016/2026', prazo=1)
        competencia = CompetenciaPagamento.objects.create(
            contrato=contrato,
            periodo_inicio=date(2026, 1, 1),
            periodo_fim=date(2026, 1, 31),
            status=CompetenciaPagamento.Status.PAGAMENTO_PENDENTE,
            valor_liberado_sugerido=Decimal('100.00'),
        )

        form = CompetenciaPagamentoExecucaoV2Form(competencia=competencia, instance=competencia)

        self.assertEqual(form.fields['gestor_pagamento'].initial, contrato.gestor_contrato)

    def test_validacao_de_upload_pdf_rejeita_arquivo_corrompido(self):
        with self.assertRaisesMessage(ValidationError, 'O arquivo enviado não é um PDF válido ou está corrompido.'):
            validar_upload_pdf(SimpleUploadedFile('corrompido.pdf', b'conteudo invalido', content_type='application/pdf'))

    def test_medicao_persiste_checkbox_de_pro_rata(self):
        contrato = self.criar_contrato(prazo=2)
        item = self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato, titulo='Documento mensal')
        contrato.gerar_competencias()
        competencia = contrato.competencias.order_by('periodo_inicio').first()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', pdf_minimo_valido(), content_type='application/pdf')},
        )

        response = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
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

        response = self.client.post(reverse('contratos:competencias_generate', args=[contrato.pk]))

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertEqual(contrato.competencias.count(), 0)

    def test_sem_itens_no_contrato_nao_gera_competencias(self):
        contrato = self.criar_contrato(numero='098/2026')
        self.criar_checklist_ativo(contrato)
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(reverse('contratos:competencias_generate', args=[contrato.pk]), follow=True)

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]))
        self.assertContains(response, 'Cadastre ao menos um item no contrato antes de gerar as competências.')
        self.assertEqual(contrato.competencias.count(), 0)

    def test_nao_gera_competencias_sem_processos_sei_mesmo_em_contrato_legado(self):
        contrato = self.criar_contrato(numero='099/2026')
        contrato.processo_sei_gestao_numero = ''
        contrato.processo_sei_gestao_url = ''
        contrato.processo_sei_execucao_numero = ''
        contrato.processo_sei_execucao_url = ''
        contrato.save(update_fields=[
            'processo_sei_gestao_numero',
            'processo_sei_gestao_url',
            'processo_sei_execucao_numero',
            'processo_sei_execucao_url',
            'atualizado_em',
        ])
        self.criar_checklist_ativo(contrato)
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(reverse('contratos:competencias_generate', args=[contrato.pk]))

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertEqual(contrato.competencias.count(), 0)

    def test_gera_competencias_da_vigencia_e_nao_duplica(self):
        contrato = self.criar_contrato(prazo=2)
        self.criar_item_contrato(contrato, ordem=1, quantidade='1.00', unitario='100.00')
        self.criar_checklist_ativo(contrato)
        self.client.login(username='gestor_v2', password='123')

        url = reverse('contratos:competencias_generate', args=[contrato.pk])
        self.client.post(url)
        self.client.post(url)

        competencias = list(contrato.competencias.order_by('periodo_inicio'))
        self.assertEqual(len(competencias), 2)
        self.assertEqual(competencias[0].periodo_inicio, date(2026, 1, 1))
        self.assertEqual(competencias[1].periodo_inicio, date(2026, 2, 1))
        self.assertEqual(competencias[0].status, CompetenciaPagamento.Status.CHECKLIST_PENDENTE)

    def test_criador_do_contrato_pode_gerar_competencias_mesmo_sem_gestor(self):
        contrato = self.criar_contrato(numero='002/2026', prazo=2, gestor=None, criado_por=self.criador)
        self.criar_item_contrato(contrato, ordem=1, quantidade='1.00', unitario='100.00')
        self.criar_checklist_ativo(contrato)
        self.client.login(username='criador_v2', password='123')

        response = self.client.post(reverse('contratos:competencias_generate', args=[contrato.pk]))

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertEqual(contrato.competencias.count(), 2)

    def test_detalhe_renderiza_processos_sei(self):
        contrato = self.criar_contrato(numero='013/2026')
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Processos SEI')
        self.assertContains(response, contrato.processo_sei_gestao_numero)
        self.assertContains(response, contrato.processo_sei_execucao_url)

    def test_criador_do_contrato_pode_cadastrar_checklist_e_formulario(self):
        contrato = self.criar_contrato(numero='003/2026', gestor=None, criado_por=self.criador)
        self.client.login(username='criador_v2', password='123')

        response_checklist = self.client.post(
            reverse('contratos:checklist_create', args=[contrato.pk]),
            {
                'nome': 'Checklist do criador',
                'descricao': 'Versão criada pelo responsável pelo cadastro',
                'observacoes': '',
                'ativo': 'on',
            },
        )
        response_formulario = self.client.post(
            reverse('contratos:avaliacao_form_create', args=[contrato.pk]),
            {
                'nome': 'Avaliação do criador',
                'descricao': 'Modelo criado por quem cadastrou o contrato',
                'observacoes': '',
                'ativo': 'on',
            },
        )

        self.assertRedirects(response_checklist, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertRedirects(response_formulario, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertTrue(contrato.checklist_modelos.filter(nome='Checklist do criador').exists())
        self.assertTrue(contrato.formularios_avaliacao.filter(nome='Avaliação do criador').exists())

    def test_terceiro_sem_gestao_continua_bloqueado_nos_cadastros_estruturantes(self):
        contrato = self.criar_contrato(numero='004/2026', gestor=None, criado_por=self.criador)
        self.client.login(username='operador_v2', password='123')

        response = self.client.post(
            reverse('contratos:checklist_create', args=[contrato.pk]),
            {
                'nome': 'Checklist indevido',
                'descricao': 'Não deveria ser criado',
                'observacoes': '',
                'ativo': 'on',
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]))
        self.assertContains(response, 'Somente o gestor do contrato, o criador do contrato ou administradores do sistema podem executar esta ação.')
        self.assertFalse(contrato.checklist_modelos.filter(nome='Checklist indevido').exists())

    def test_detalhe_renderiza_blocos_de_checklist_avaliacao_e_competencias(self):
        contrato = self.criar_contrato(prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_documento_importante(contrato, nome='Minuta assinada')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Documentos importantes')
        self.assertContains(response, 'Minuta assinada')
        self.assertContains(response, 'Monitoramento de prazos')
        self.assertContains(response, 'Competências geradas')
        self.assertContains(response, 'Checklist')
        self.assertContains(response, 'Pagamento')

    def test_detalhe_ordena_competencias_abertas_em_ordem_crescente_e_pagas_ao_final(self):
        contrato = self.criar_contrato(numero='016/2026', prazo=3)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencias = list(contrato.competencias.order_by('periodo_inicio'))
        competencias[2].status = CompetenciaPagamento.Status.PAGA
        competencias[2].data_pagamento = date(2026, 3, 31)
        competencias[2].save(update_fields=['status', 'data_pagamento', 'atualizado_em'])
        self.client.login(username='gestor_v2', password='123')

        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        competencias_ordenadas = response.context['competencias_ordenadas']
        self.assertEqual(
            [competencia.periodo_inicio for competencia in competencias_ordenadas],
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
        )
        self.assertEqual(competencias_ordenadas[-1].status, CompetenciaPagamento.Status.PAGA)

    def test_criador_pode_cadastrar_documento_importante(self):
        contrato = self.criar_contrato(numero='005/2026', criado_por=self.criador)
        self.client.login(username='criador_v2', password='123')

        response = self.client.post(
            reverse('contratos:documento_importante_create', args=[contrato.pk]),
            {
                'nome': 'Ofício de autorização',
                'arquivo': SimpleUploadedFile('oficio.pdf', pdf_minimo_valido(), content_type='application/pdf'),
            },
        )

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        documento = contrato.documentos_importantes.get(nome='Ofício de autorização')
        self.assertEqual(documento.criado_por, self.criador)

    def test_gestor_pode_editar_e_excluir_documento_importante(self):
        contrato = self.criar_contrato(numero='006/2026', criado_por=self.criador)
        documento = self.criar_documento_importante(contrato, nome='Documento inicial', usuario=self.criador)
        self.client.login(username='gestor_v2', password='123')

        response_update = self.client.post(
            reverse('contratos:documento_importante_update', args=[documento.pk]),
            {
                'nome': 'Documento revisado',
                'arquivo': SimpleUploadedFile('revisado.pdf', pdf_minimo_valido(), content_type='application/pdf'),
            },
        )
        response_delete = self.client.post(
            reverse('contratos:documento_importante_delete', args=[documento.pk]),
        )

        self.assertRedirects(response_update, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertRedirects(response_delete, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        self.assertFalse(contrato.documentos_importantes.filter(pk=documento.pk).exists())

    def test_autor_do_documento_pode_ver_acoes_e_editar_mesmo_sem_ser_criador_do_contrato(self):
        contrato = self.criar_contrato(numero='006A/2026', criado_por=self.criador)
        documento = self.criar_documento_importante(contrato, nome='Documento do operador', usuario=self.operador)
        self.client.login(username='operador_v2', password='123')

        response_detail = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))
        response_update = self.client.post(
            reverse('contratos:documento_importante_update', args=[documento.pk]),
            {
                'nome': 'Documento atualizado pelo autor',
                'arquivo': SimpleUploadedFile('autor.pdf', pdf_minimo_valido(), content_type='application/pdf'),
            },
        )

        self.assertContains(response_detail, 'Ações')
        self.assertContains(response_detail, reverse('contratos:documento_importante_update', args=[documento.pk]))
        self.assertRedirects(response_update, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)
        documento.refresh_from_db()
        self.assertEqual(documento.nome, 'Documento atualizado pelo autor')

    def test_terceiro_nao_pode_gerenciar_documento_importante(self):
        contrato = self.criar_contrato(numero='007/2026', criado_por=self.criador)
        documento = self.criar_documento_importante(contrato)
        self.client.login(username='operador_v2', password='123')

        response = self.client.post(
            reverse('contratos:documento_importante_update', args=[documento.pk]),
            {
                'nome': 'Tentativa indevida',
                'arquivo': SimpleUploadedFile('indevido.pdf', pdf_minimo_valido(), content_type='application/pdf'),
            },
            follow=True,
        )

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]))
        self.assertContains(response, 'Somente o gestor do contrato, o criador do contrato, o autor do documento ou administradores do sistema podem editar este documento.')
        documento.refresh_from_db()
        self.assertEqual(documento.nome, 'Documento base')

    def test_criador_cobre_avaliacao_fiscal_quando_contrato_ainda_nao_tem_fiscais(self):
        contrato = self.criar_contrato(
            numero='008/2026',
            criado_por=self.criador,
        )
        contrato.fiscal_administrativo = None
        contrato.fiscal_tecnico = None
        contrato.save(update_fields=['fiscal_administrativo', 'fiscal_tecnico', 'atualizado_em'])

        self.assertTrue(usuario_pode_preencher_avaliacao_fiscal_v2(self.criador, contrato))
        self.assertFalse(usuario_pode_preencher_avaliacao_fiscal_v2(self.operador, contrato))

    def test_criador_cobre_avaliacao_gestor_quando_contrato_ainda_nao_tem_gestor(self):
        contrato = self.criar_contrato(
            numero='009/2026',
            criado_por=self.criador,
        )
        contrato.gestor_contrato = None
        contrato.save(update_fields=['gestor_contrato', 'atualizado_em'])

        self.assertTrue(usuario_pode_preencher_avaliacao_gestor_v2(self.criador, contrato))
        self.assertFalse(usuario_pode_preencher_avaliacao_gestor_v2(self.operador, contrato))

    def test_equipe_passa_a_ter_acesso_na_sua_area_quando_for_definida(self):
        contrato = self.criar_contrato(numero='010/2026', criado_por=self.criador)

        self.assertTrue(usuario_pode_preencher_avaliacao_fiscal_v2(self.fiscal_adm, contrato))
        self.assertTrue(usuario_pode_preencher_avaliacao_fiscal_v2(self.fiscal_tec, contrato))
        self.assertTrue(usuario_pode_preencher_avaliacao_gestor_v2(self.gestor, contrato))

    def test_ativar_novo_checklist_atualiza_competencias_em_aberto(self):
        contrato = self.criar_contrato()
        self.criar_item_contrato(contrato)
        checklist_v1 = self.criar_checklist_ativo(contrato, nome='Checklist v1', titulo='FGTS')
        contrato.gerar_competencias()
        competencia = contrato.competencias.first()
        self.assertEqual(list(competencia.checklist_itens.values_list('titulo', flat=True)), ['FGTS'])

        checklist_v2 = ChecklistModelo.objects.create(
            contrato=contrato,
            nome='Checklist v2',
            descricao='Nova versão',
            ativo=True,
        )
        ChecklistModeloItem.objects.create(modelo=checklist_v2, ordem=1, titulo='INSS', obrigatorio=True)
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
        checklist_url = reverse('contratos:competencia_checklist', args=[competencia.pk])
        medicao_url = reverse('contratos:competencia_medicao', args=[competencia.pk])
        pagamento_url = reverse('contratos:competencia_pagamento', args=[competencia.pk])

        response_checklist = self.client.post(
            checklist_url,
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', pdf_minimo_valido(), content_type='application/pdf')},
        )
        self.assertEqual(response_checklist.status_code, 302)

        response_medicao = self.client.post(medicao_url, {f'quantidade_{contrato.itens.get().pk}': '2.00'})
        self.assertEqual(response_medicao.status_code, 302)

        response_pagamento = self.client.post(
            pagamento_url,
            {
                'nota_fiscal_fatura': SimpleUploadedFile('nf.pdf', pdf_minimo_valido(), content_type='application/pdf'),
                'valor_nota_fiscal': '115.00',
                'retencao_ir': '5.00',
                'retencao_inss': '5.00',
                'retencao_iss': '3.00',
                'retencao_pis_pasep': '1.00',
                'retencao_cofins': '1.00',
                'atestado_realizacao': SimpleUploadedFile('atestado.pdf', pdf_minimo_valido(), content_type='application/pdf'),
                'valor_liberado_final': '100.00',
                'gestor_pagamento': str(self.gestor.pk),
                'gestor_pagamento_em_exercicio': '',
                'coordenadora_pagamento': str(self.operador.pk),
                'coordenadora_em_exercicio': 'on',
                'diretora_pagamento': str(self.fiscal_adm.pk),
                'diretora_em_exercicio': '',
                'subsecretario_pagamento': str(self.fiscal_tec.pk),
                'subsecretario_em_exercicio': '',
                'data_pagamento': '2026-01-31',
                'justificativa_divergencia': '',
            },
        )
        competencia.refresh_from_db()

        self.assertEqual(response_pagamento.status_code, 302)
        self.assertEqual(competencia.status, CompetenciaPagamento.Status.PAGAMENTO_REGISTRADO)
        self.assertEqual(competencia.valor_medido, Decimal('100.00'))
        self.assertEqual(competencia.valor_nota_fiscal, Decimal('115.00'))
        self.assertEqual(competencia.total_retencoes, Decimal('15.00'))
        self.assertEqual(competencia.valor_liberado_sugerido, Decimal('100.00'))
        self.assertEqual(competencia.valor_liberado_final, Decimal('100.00'))

        # Agora inicia a geração assíncrona, consulta o status e faz o download do PDF pronto.
        start_url = reverse('contratos:competencia_download_docs_start', args=[competencia.pk])
        response_start = self.client.post(start_url)
        competencia.refresh_from_db()
        self.assertEqual(response_start.status_code, 200)
        job = ExportacaoDocumentosCompetencia.objects.get(pk=response_start.json()['job_id'])
        status_url = reverse('contratos:competencia_download_docs_status', args=[job.pk])
        response_status = self.client.get(status_url)
        self.assertEqual(response_status.status_code, 200)
        self.assertEqual(response_status.json()['status'], ExportacaoDocumentosCompetencia.Status.CONCLUIDO)

        download_url = reverse('contratos:competencia_download_docs_file', args=[job.pk])
        response_download = self.client.get(download_url)
        self.assertEqual(response_download.status_code, 200)
        self.assertEqual(response_download['Content-Type'], 'application/pdf')
        self.assertEqual(competencia.status, CompetenciaPagamento.Status.PAGA)

        doc = gerar_ultima_folha_atestado('/root/aplicacoesspi/docs/papel-timbrado-spi.docx', contrato, competencia)
        texto = '\n'.join(paragrafo.text for paragrafo in doc.paragraphs)
        tabela_texto = '\n'.join(celula.text for tabela in doc.tables for linha in tabela.rows for celula in linha.cells)
        self.assertIn('ATESTADO DE REALIZAÇÃO', texto)
        self.assertIn('ACOMPANHAMENTO DE PAGAMENTO', tabela_texto)
        self.assertIn('CHECKLIST DE VERIFICAÇÃO', tabela_texto)
        self.assertIn(contrato.processo_sei_gestao_numero, tabela_texto)
        self.assertIn('VIGÊNCIA DO CONTRATO', tabela_texto)
        self.assertIn('Coordenadora - em exercício', texto)

    def test_exportacao_documentos_impede_acesso_de_outro_usuario(self):
        contrato = self.criar_contrato(numero='020/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='10.00')
        self.criar_checklist_ativo(contrato, titulo='Documento mensal')
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.status = CompetenciaPagamento.Status.PAGA
        competencia.valor_nota_fiscal = Decimal('10.00')
        competencia.valor_liberado_final = Decimal('10.00')
        competencia.nota_fiscal_fatura = SimpleUploadedFile('nf.pdf', pdf_minimo_valido(), content_type='application/pdf')
        competencia.save()

        self.client.login(username='gestor_v2', password='123')
        response_start = self.client.post(reverse('contratos:competencia_download_docs_start', args=[competencia.pk]))
        job = ExportacaoDocumentosCompetencia.objects.get(pk=response_start.json()['job_id'])
        self.client.logout()

        self.client.login(username='operador_v2', password='123')
        response_status = self.client.get(reverse('contratos:competencia_download_docs_status', args=[job.pk]))
        self.assertEqual(response_status.status_code, 403)

    def test_exportacao_documentos_informa_qual_pdf_esta_corrompido(self):
        contrato = self.criar_contrato(numero='021/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='10.00')
        self.criar_checklist_ativo(contrato, titulo='Documento mensal')
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        checklist_item = competencia.checklist_itens.get()
        ChecklistCompetenciaAnexo.objects.create(
            item=checklist_item,
            arquivo=SimpleUploadedFile('corrompido.pdf', b'nao eh pdf', content_type='application/pdf'),
            nome_exibicao='corrompido.pdf',
        )
        competencia.status = CompetenciaPagamento.Status.PAGA
        competencia.valor_nota_fiscal = Decimal('10.00')
        competencia.valor_liberado_final = Decimal('10.00')
        competencia.nota_fiscal_fatura = SimpleUploadedFile('nf.pdf', pdf_minimo_valido(), content_type='application/pdf')
        competencia.save()

        def fake_converter_docx_para_pdf(docx_file, output_dir):
            """Gera PDFs mínimos em disco para isolar o teste na etapa de mesclagem."""

            caminho_pdf = Path(output_dir) / f'{Path(docx_file).stem}.pdf'
            caminho_pdf.write_bytes(pdf_minimo_valido())
            return caminho_pdf

        self.client.login(username='gestor_v2', password='123')
        with patch('contratos.views._converter_docx_para_pdf', side_effect=fake_converter_docx_para_pdf):
            response_start = self.client.post(reverse('contratos:competencia_download_docs_start', args=[competencia.pk]))

        self.assertEqual(response_start.status_code, 200)
        job = ExportacaoDocumentosCompetencia.objects.get(pk=response_start.json()['job_id'])
        self.assertEqual(job.status, ExportacaoDocumentosCompetencia.Status.ERRO)
        self.assertIn('Checklist - Documento mensal', job.erro_detalhe)

        response_status = self.client.get(reverse('contratos:competencia_download_docs_status', args=[job.pk]))
        self.assertEqual(response_status.status_code, 200)
        self.assertIn('Checklist - Documento mensal', response_status.json()['erro_detalhe'])

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
            reverse('contratos:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', pdf_minimo_valido(), content_type='application/pdf')},
        )
        self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{contrato.itens.get().pk}': '2.00'},
        )
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()

        response_invalido = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': '',
                'observacoes': '',
            },
        )
        self.assertContains(response_invalido, 'Informe a justificativa do fiscal')

        response_pendente = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Serviço parcialmente entregue.',
                'observacoes': 'Avaliação mensal',
            },
        )
        competencia.refresh_from_db()
        avaliacao.refresh_from_db()
        resposta.refresh_from_db()

        self.assertEqual(response_pendente.status_code, 302)
        self.assertEqual(competencia.status, CompetenciaPagamento.Status.AVALIACAO_PENDENTE)
        self.assertIsNone(avaliacao.concluida_em)
        self.assertEqual(resposta.nota_fiscal_valor, Decimal('1.00'))
        self.assertIsNone(resposta.nota_gestor_valor)
        self.assertEqual(resposta.justificativa_fiscal, 'Serviço parcialmente entregue.')
        self.assertEqual(resposta.manifestacao_gestor_item, '')
        self.assertIsNotNone(resposta.justificativa_fiscal_preenchida_por)
        self.assertIsNotNone(resposta.justificativa_fiscal_preenchida_em)
        self.assertEqual(competencia.etapas[2], ('Avaliação', 'pending'))

        response_form = self.client.get(reverse('contratos:competencia_avaliacao', args=[competencia.pk]))
        self.assertContains(response_form, 'Preenchido por')

        response_valido = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_gestor_{resposta.pk}': '1.00',
                f'manifestacao_gestor_item_{resposta.pk}': 'Ciente da justificativa e da retenção neste item.',
                'observacoes': 'Avaliação mensal',
            },
        )
        competencia.refresh_from_db()
        avaliacao.refresh_from_db()
        resposta.refresh_from_db()

        self.assertEqual(response_valido.status_code, 302)
        self.assertEqual(competencia.status, CompetenciaPagamento.Status.PAGAMENTO_PENDENTE)
        self.assertEqual(avaliacao.nota_final, Decimal('1.00'))
        self.assertEqual(avaliacao.percentual_liberacao_sugerido, Decimal('75.00'))
        self.assertEqual(competencia.valor_liberado_sugerido, Decimal('75.00'))
        self.assertEqual(resposta.nota_gestor_valor, Decimal('1.00'))
        self.assertEqual(resposta.manifestacao_gestor_item, 'Ciente da justificativa e da retenção neste item.')
        self.assertIsNotNone(resposta.manifestacao_gestor_item_preenchida_por)
        self.assertIsNotNone(resposta.manifestacao_gestor_item_preenchida_em)
        self.assertEqual(competencia.etapas[2], ('Avaliação', 'done'))

    def test_avaliacao_ignora_ajustes_do_fechamento_quando_a_secao_ainda_nao_estava_liberada(self):
        contrato = self.criar_contrato(numero='011-M/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.status = CompetenciaPagamento.Status.AVALIACAO_PENDENTE
        competencia.valor_nota_fiscal = Decimal('100.00')
        competencia.avaliacao_assinada = SimpleUploadedFile('avaliacao.pdf', pdf_minimo_valido(), content_type='application/pdf')
        competencia.save(update_fields=['medicao_concluida_em', 'status', 'valor_nota_fiscal', 'avaliacao_assinada', 'atualizado_em'])
        avaliacao = criar_avaliacao_shell_competencia_v2(competencia, contrato.formulario_avaliacao_ativo)
        resposta = avaliacao.itens.get()

        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Serviço parcialmente entregue.',
                f'nota_gestor_{resposta.pk}': '1.00',
                f'manifestacao_gestor_item_{resposta.pk}': 'Ciente da justificativa e da retenção neste item.',
                'observacoes': 'Avaliação com ajuste manual.',
                'valor_liberado_final': '40.00',
                'gestor_pagamento': str(self.gestor.pk),
                'gestor_pagamento_nome_manual': '',
                'gestor_pagamento_em_exercicio': 'on',
                'coordenadora_pagamento': '',
                'coordenadora_pagamento_nome_manual': 'Coordenadora Interina',
                'coordenadora_em_exercicio': 'on',
                'diretora_pagamento': str(self.fiscal_adm.pk),
                'diretora_pagamento_nome_manual': '',
                'diretora_em_exercicio': '',
                'subsecretario_pagamento': '',
                'subsecretario_pagamento_nome_manual': 'Subsecretário Adjunto',
                'subsecretario_em_exercicio': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        avaliacao.refresh_from_db()
        competencia.refresh_from_db()
        self.assertIsNone(avaliacao.nota_final_manual)
        self.assertEqual(avaliacao.nota_final, Decimal('1.00'))
        self.assertIsNone(avaliacao.percentual_liberacao_manual)
        self.assertEqual(avaliacao.percentual_liberacao_sugerido, Decimal('75.00'))
        self.assertIsNone(competencia.valor_liberado_final_manual)
        self.assertEqual(competencia.coordenadora_pagamento_nome_manual, '')
        self.assertFalse(competencia.coordenadora_em_exercicio)

    def test_formulario_da_avaliacao_exibe_faixa_automatica_e_bloqueada(self):
        contrato = self.criar_contrato(numero='011-J/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.status = CompetenciaPagamento.Status.AVALIACAO_PENDENTE
        competencia.valor_nota_fiscal = Decimal('100.00')
        competencia.save(update_fields=['medicao_concluida_em', 'status', 'valor_nota_fiscal', 'atualizado_em'])
        avaliacao = criar_avaliacao_shell_competencia_v2(competencia, contrato.formulario_avaliacao_ativo)
        resposta = avaliacao.itens.get()
        resposta.nota_fiscal_valor = Decimal('3.00')
        resposta.nota_gestor_valor = Decimal('3.00')
        resposta.nota_valor = Decimal('3.00')
        resposta.save(update_fields=['nota_fiscal_valor', 'nota_gestor_valor', 'nota_valor', 'atualizado_em'])

        form = AvaliacaoCompetenciaV2Form(avaliacao=avaliacao, pode_preencher_fiscal=True, pode_preencher_gestor=True)

        self.assertEqual(form.fields['percentual_liberacao_aprovado'].initial, Decimal('100.00'))
        self.assertTrue(form.fields['percentual_liberacao_aprovado'].disabled)
        self.assertEqual(form.fields['percentual_liberacao_aprovado'].widget.attrs.get('readonly'), 'readonly')

    def test_avaliacao_assinada_forca_nota_final_automatica_e_bloqueada(self):
        contrato = self.criar_contrato(numero='011-M/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.status = CompetenciaPagamento.Status.AVALIACAO_PENDENTE
        competencia.valor_nota_fiscal = Decimal('100.00')
        competencia.save(update_fields=['medicao_concluida_em', 'status', 'valor_nota_fiscal', 'atualizado_em'])
        avaliacao = criar_avaliacao_shell_competencia_v2(competencia, contrato.formulario_avaliacao_ativo)
        resposta = avaliacao.itens.get()

        self.client.login(username='gestor_v2', password='123')
        response = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Entrega parcial.',
                f'nota_gestor_{resposta.pk}': '1.00',
                f'manifestacao_gestor_item_{resposta.pk}': 'Ciente.',
                'observacoes': 'Avaliação assinada.',
                'nota_final_aprovada': '0.00',
                'percentual_liberacao_aprovado': '80.00',
                'valor_liberado_final': '40.00',
                'avaliacao_assinada': SimpleUploadedFile('avaliacao.pdf', pdf_minimo_valido(), content_type='application/pdf'),
            },
        )

        self.assertEqual(response.status_code, 302)
        avaliacao.refresh_from_db()
        competencia.refresh_from_db()
        self.assertIsNone(avaliacao.nota_final_manual)
        self.assertEqual(avaliacao.nota_final, Decimal('1.00'))

        form = AvaliacaoCompetenciaV2Form(avaliacao=avaliacao, pode_preencher_fiscal=True, pode_preencher_gestor=True)
        self.assertEqual(form.fields['nota_final_aprovada'].initial, Decimal('1.00'))
        self.assertEqual(form.fields['nota_final_aprovada'].widget.attrs.get('readonly'), 'readonly')

    def test_fechamento_da_avaliacao_fica_bloqueado_antes_dos_requisitos(self):
        contrato = self.criar_contrato(numero='011-L/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.status = CompetenciaPagamento.Status.AVALIACAO_PENDENTE
        competencia.save(update_fields=['medicao_concluida_em', 'status', 'atualizado_em'])
        avaliacao = criar_avaliacao_shell_competencia_v2(competencia, contrato.formulario_avaliacao_ativo)

        form = AvaliacaoCompetenciaV2Form(avaliacao=avaliacao, pode_preencher_fiscal=True, pode_preencher_gestor=True)

        self.assertFalse(form.fechamento_avaliacao_liberado)
        self.assertFalse(form.fechamento_avaliacao_concluido)
        self.assertTrue(form.fields['nota_final_aprovada'].disabled)
        self.assertTrue(form.fields['percentual_liberacao_aprovado'].disabled)
        self.assertTrue(form.fields['valor_liberado_final'].disabled)

    def test_fechamento_da_avaliacao_permanece_bloqueado_apos_conclusao(self):
        contrato = self.criar_contrato(numero='011-K/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.status = CompetenciaPagamento.Status.AVALIACAO_PENDENTE
        competencia.valor_nota_fiscal = Decimal('100.00')
        competencia.avaliacao_assinada = SimpleUploadedFile('avaliacao.pdf', pdf_minimo_valido(), content_type='application/pdf')
        competencia.save(update_fields=['medicao_concluida_em', 'status', 'valor_nota_fiscal', 'avaliacao_assinada', 'atualizado_em'])
        avaliacao = criar_avaliacao_shell_competencia_v2(competencia, contrato.formulario_avaliacao_ativo)
        resposta = avaliacao.itens.get()
        resposta.nota_fiscal_valor = Decimal('3.00')
        resposta.nota_gestor_valor = Decimal('3.00')
        resposta.nota_valor = Decimal('3.00')
        resposta.save(update_fields=['nota_fiscal_valor', 'nota_gestor_valor', 'nota_valor', 'atualizado_em'])
        avaliacao.concluida_em = timezone.now()
        avaliacao.save(update_fields=['concluida_em', 'atualizado_em'])

        form = AvaliacaoCompetenciaV2Form(avaliacao=avaliacao, pode_preencher_fiscal=True, pode_preencher_gestor=True)

        self.assertTrue(form.fechamento_avaliacao_liberado)
        self.assertTrue(form.fechamento_avaliacao_concluido)
        self.assertTrue(form.fields['nota_final_aprovada'].disabled)
        self.assertTrue(form.fields['percentual_liberacao_aprovado'].disabled)
        self.assertTrue(form.fields['valor_liberado_final'].disabled)

    def test_atestado_usa_nome_manual_e_sufixo_em_exercicio_na_assinatura(self):
        contrato = self.criar_contrato(numero='011-N/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.coordenadora_pagamento_nome_manual = 'Coordenadora Interina'
        competencia.coordenadora_em_exercicio = True
        competencia.gestor_pagamento = self.gestor
        competencia.gestor_pagamento_em_exercicio = True
        competencia.valor_liberado_final_manual = Decimal('45.00')
        competencia.valor_liberado_final = Decimal('45.00')
        competencia.save(
            update_fields=[
                'coordenadora_pagamento_nome_manual',
                'coordenadora_em_exercicio',
                'gestor_pagamento',
                'gestor_pagamento_em_exercicio',
                'valor_liberado_final_manual',
                'valor_liberado_final',
                'atualizado_em',
            ]
        )

        doc = gerar_ultima_folha_atestado('/root/aplicacoesspi/docs/papel-timbrado-spi.docx', contrato, competencia)
        texto = '\n'.join(paragrafo.text for paragrafo in doc.paragraphs)

        self.assertIn('Coordenadora Interina - em exercício', texto)
        self.assertIn('gestor_v2 - em exercício', texto)

    def test_detalhe_explica_na_interface_por_que_as_etapas_ainda_estao_bloqueadas(self):
        contrato = self.criar_contrato(numero='011-A/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()

        self.client.login(username='gestor_v2', password='123')
        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Conclua a medição para liberar a avaliação.')
        self.assertContains(response, 'Conclua a medição para liberar o checklist.')
        self.assertContains(response, 'Conclua a medição para liberar o download dos documentos.')
        self.assertContains(response, 'Conclua a medição para avançar até a Ordem Bancária.')

    def test_download_documentos_retorna_motivo_claro_quando_fluxo_esta_fora_de_ordem(self):
        contrato = self.criar_contrato(numero='011-B/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response = self.client.post(reverse('contratos:competencia_download_docs_start', args=[competencia.pk]))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], 'Conclua a medição para liberar o download dos documentos.')

    def test_ob_mostra_feedback_claro_quando_download_ainda_nao_foi_gerado(self):
        contrato = self.criar_contrato(numero='011-C/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.checklist_concluido_em = timezone.now()
        competencia.status = CompetenciaPagamento.Status.DOWNLOAD_PENDENTE
        competencia.save(update_fields=['medicao_concluida_em', 'checklist_concluido_em', 'status', 'atualizado_em'])

        self.client.login(username='gestor_v2', password='123')
        response = self.client.get(reverse('contratos:competencia_ob', args=[competencia.pk]), follow=True)

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]))
        self.assertContains(response, 'Gere o pacote documental para liberar a Ordem Bancária.')

    def test_fluxo_assincrono_da_avaliacao_mantem_nota_do_fiscal_sem_preencher_nota_do_gestor(self):
        contrato = self.criar_contrato(numero='012/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', pdf_minimo_valido(), content_type='application/pdf')},
        )
        self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{contrato.itens.get().pk}': '2.00'},
        )
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()

        self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Serviço parcialmente entregue.',
                'observacoes': 'Avaliação mensal',
            },
        )
        resposta.refresh_from_db()
        self.assertEqual(resposta.nota_fiscal_valor, Decimal('1.00'))
        self.assertIsNone(resposta.nota_gestor_valor)

        response_form = self.client.get(reverse('contratos:competencia_avaliacao', args=[competencia.pk]))
        self.assertContains(response_form, '0.00 - Insatisfatório')

    def test_fiscal_pode_salvar_mesmo_com_select_do_gestor_vindo_zerado_no_post(self):
        contrato = self.criar_contrato(numero='013/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', pdf_minimo_valido(), content_type='application/pdf')},
        )
        self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{contrato.itens.get().pk}': '2.00'},
        )
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()

        response = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Serviço parcialmente entregue.',
                f'nota_gestor_{resposta.pk}': '0.00',
                f'manifestacao_gestor_item_{resposta.pk}': '',
                'observacoes': 'Avaliação mensal',
            },
        )
        resposta.refresh_from_db()
        competencia.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(resposta.nota_fiscal_valor, Decimal('1.00'))
        self.assertIsNone(resposta.nota_gestor_valor)
        self.assertEqual(competencia.status, CompetenciaPagamento.Status.AVALIACAO_PENDENTE)

    def test_avaliacao_conclui_quando_fiscal_da_nota_maxima_e_gestor_da_nota_baixa_com_manifestacao(self):
        contrato = self.criar_contrato(numero='014/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', pdf_minimo_valido(), content_type='application/pdf')},
        )
        self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{contrato.itens.get().pk}': '2.00'},
        )
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()

        self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '3.00',
                f'justificativa_fiscal_{resposta.pk}': '',
                'observacoes': 'Fiscal sem ressalvas',
            },
        )
        response = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_gestor_{resposta.pk}': '0.00',
                f'manifestacao_gestor_item_{resposta.pk}': 'Gestor registrou inconformidade.',
                'observacoes': 'Gestor apontou restrições',
            },
        )
        competencia.refresh_from_db()
        avaliacao.refresh_from_db()
        resposta.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(competencia.status, CompetenciaPagamento.Status.PAGAMENTO_PENDENTE)
        self.assertIsNotNone(avaliacao.concluida_em)
        self.assertEqual(resposta.nota_fiscal_valor, Decimal('3.00'))
        self.assertEqual(resposta.nota_gestor_valor, Decimal('0.00'))
        self.assertEqual(resposta.nota_valor, Decimal('0.00'))

    def test_relatorio_da_avaliacao_exporta_itens_quando_competencia_exige_qualidade(self):
        contrato = self.criar_contrato(numero='011/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        checklist_item = competencia.checklist_itens.get()

        self.client.login(username='gestor_v2', password='123')
        self.client.post(
            reverse('contratos:competencia_checklist', args=[competencia.pk]),
            {f'arquivo_{checklist_item.pk}': SimpleUploadedFile('doc.pdf', pdf_minimo_valido(), content_type='application/pdf')},
        )
        self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{contrato.itens.get().pk}': '2.00'},
        )
        avaliacao = competencia.avaliacao_qualidade
        resposta = avaliacao.itens.get()
        self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Serviço parcialmente entregue.',
                'observacoes': 'Avaliação mensal',
            },
        )
        self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_gestor_{resposta.pk}': '1.00',
                f'manifestacao_gestor_item_{resposta.pk}': 'Ciente da justificativa e da retenção neste item.',
                'observacoes': 'Avaliação mensal',
            },
        )

        doc = gerar_relatorio_avaliacao_competencia('/root/aplicacoesspi/docs/papel-timbrado-spi.docx', contrato, competencia)
        texto = '\n'.join(paragrafo.text for paragrafo in doc.paragraphs)
        tabela_texto = '\n'.join(celula.text for tabela in doc.tables for linha in tabela.rows for celula in linha.cells)

        self.assertIn('RELATÓRIO DE AVALIAÇÃO DE QUALIDADE', texto)
        self.assertIn('Qualidade da entrega', tabela_texto)
        self.assertIn('Serviço parcialmente entregue.', tabela_texto)
        self.assertIn('Ciente da justificativa e da retenção neste item.', tabela_texto)

    def test_nao_permita_criar_formulario_de_avaliacao_apos_gerar_competencias(self):
        contrato = self.criar_contrato()
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(
            reverse('contratos:avaliacao_form_create', args=[contrato.pk]),
            {
                'nome': 'Avaliação tardia',
                'descricao': 'Não deveria deixar',
                'ativo': 'on',
                'observacoes': '',
            },
        )

        self.assertRedirects(response, reverse('contratos:contrato_detail', args=[contrato.pk]), fetch_redirect_response=False)

    def test_auditoria_cria_e_atualiza_eventos_do_contrato(self):
        self.client.login(username='gestor_v2', password='123')

        response_create = self.client.post(reverse('contratos:contrato_create'), self.dados_contrato_post(numero='101/2026'))
        self.assertEqual(response_create.status_code, 302)
        contrato = Contrato.objects.get(numero_contrato='101/2026')

        evento_criacao = ContratoAuditoriaEvento.objects.filter(contrato=contrato).first()
        self.assertIsNotNone(evento_criacao)
        self.assertEqual(evento_criacao.tipo_evento, ContratoAuditoriaEvento.TipoEvento.CONTRATO_CRIADO)

        payload_update = self.dados_contrato_post(numero='101/2026', apelido='Contrato alterado')
        payload_update['objeto'] = 'Serviço ajustado em tela'
        response_update = self.client.post(reverse('contratos:contrato_update', args=[contrato.pk]), payload_update)
        self.assertEqual(response_update.status_code, 302)

        evento_atualizacao = ContratoAuditoriaEvento.objects.filter(
            contrato=contrato,
            tipo_evento=ContratoAuditoriaEvento.TipoEvento.CONTRATO_ATUALIZADO,
        ).first()
        self.assertIsNotNone(evento_atualizacao)
        self.assertTrue(any(change['field'] == 'apelido' for change in evento_atualizacao.payload['changes']))

    def test_auditoria_de_item_do_contrato_cobre_criacao_edicao_e_exclusao(self):
        contrato = self.criar_contrato(numero='102/2026')
        self.client.login(username='gestor_v2', password='123')

        response_create = self.client.post(
            reverse('contratos:item_create', args=[contrato.pk]),
            {
                'ordem': '1',
                'descricao': 'Item auditado',
                'codigo_siafisico': 'ABC',
                'codigo_catmat_catser': 'XYZ',
                'quantidade': '10.00',
                'valor_unitario': '12.50',
            },
        )
        self.assertEqual(response_create.status_code, 302)
        item = contrato.itens.get()

        response_update = self.client.post(
            reverse('contratos:item_update', args=[contrato.pk, item.pk]),
            {
                'ordem': '1',
                'descricao': 'Item auditado alterado',
                'codigo_siafisico': 'ABC',
                'codigo_catmat_catser': 'XYZ',
                'quantidade': '12.00',
                'valor_unitario': '13.50',
            },
        )
        self.assertEqual(response_update.status_code, 302)

        response_delete = self.client.post(reverse('contratos:item_delete', args=[contrato.pk, item.pk]))
        self.assertEqual(response_delete.status_code, 302)

        tipos = list(
            ContratoAuditoriaEvento.objects.filter(contrato=contrato).values_list('tipo_evento', flat=True)
        )
        self.assertIn(ContratoAuditoriaEvento.TipoEvento.ITEM_CRIADO, tipos)
        self.assertIn(ContratoAuditoriaEvento.TipoEvento.ITEM_ATUALIZADO, tipos)
        self.assertIn(ContratoAuditoriaEvento.TipoEvento.ITEM_EXCLUIDO, tipos)

    def test_auditoria_carregamentos_padrao_geram_eventos_resumidos(self):
        contrato = self.criar_contrato(numero='103/2026')
        checklist_padrao = self.criar_checklist_padrao_global()
        formulario_padrao = self.criar_formulario_padrao_global()
        self.client.login(username='gestor_v2', password='123')

        response_checklist = self.client.post(
            reverse('contratos:checklist_padrao_carregar', args=[contrato.pk]),
            {'checklist_padrao_id': str(checklist_padrao.pk)},
        )
        response_formulario = self.client.post(
            reverse('contratos:avaliacao_padrao_carregar', args=[contrato.pk]),
            {'formulario_padrao_id': str(formulario_padrao.pk)},
        )

        self.assertEqual(response_checklist.status_code, 302)
        self.assertEqual(response_formulario.status_code, 302)
        self.assertTrue(
            ContratoAuditoriaEvento.objects.filter(
                contrato=contrato,
                tipo_evento=ContratoAuditoriaEvento.TipoEvento.CHECKLIST_PADRAO_CARREGADO,
            ).exists()
        )
        self.assertTrue(
            ContratoAuditoriaEvento.objects.filter(
                contrato=contrato,
                tipo_evento=ContratoAuditoriaEvento.TipoEvento.FORMULARIO_PADRAO_CARREGADO,
            ).exists()
        )

    def test_auditoria_da_geracao_de_competencias_registra_contrato_e_competencias(self):
        contrato = self.criar_contrato(numero='104/2026', prazo=2)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        self.client.login(username='gestor_v2', password='123')

        response = self.client.post(reverse('contratos:competencias_generate', args=[contrato.pk]))
        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            ContratoAuditoriaEvento.objects.filter(
                contrato=contrato,
                tipo_evento=ContratoAuditoriaEvento.TipoEvento.COMPETENCIAS_GERADAS,
            ).exists()
        )
        self.assertEqual(
            CompetenciaAuditoriaEvento.objects.filter(
                competencia__contrato=contrato,
                tipo_evento=CompetenciaAuditoriaEvento.TipoEvento.COMPETENCIA_CRIADA,
            ).count(),
            contrato.competencias.count(),
        )

    def test_auditoria_da_medicao_gera_evento_da_competencia(self):
        contrato = self.criar_contrato(numero='105/2026', prazo=1)
        item = self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response = self.client.post(reverse('contratos:competencia_medicao', args=[competencia.pk]), {f'quantidade_{item.pk}': '2.00'})
        self.assertEqual(response.status_code, 302)

        evento = CompetenciaAuditoriaEvento.objects.filter(
            competencia=competencia,
            tipo_evento=CompetenciaAuditoriaEvento.TipoEvento.MEDICAO_ATUALIZADA,
        ).first()
        self.assertIsNotNone(evento)
        self.assertIn('medicoes_alteradas', evento.payload['extra'])

    def test_medicao_exibe_fluxo_sequencial_e_bloqueia_nota_principal_no_inicio(self):
        contrato = self.criar_contrato(numero='107/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response = self.client.get(reverse('contratos:competencia_medicao', args=[competencia.pk]))

        self.assertContains(response, '1. Medição')
        self.assertContains(response, '2. Nota Fiscal Principal')
        self.assertContains(response, '3. Nota Fiscal Adicional')
        self.assertContains(response, 'Observações finais')
        self.assertContains(response, 'Fica sempre disponível.')
        self.assertNotContains(response, 'Começa liberada.')
        self.assertNotContains(response, 'Fica sempre disponível ao final da tela.')
        self.assertContains(response, 'Salve a etapa de medição para liberar o preenchimento da nota fiscal principal.')
        self.assertContains(response, 'Salve a medição e a nota fiscal principal para liberar o preenchimento da nota fiscal adicional.')

    def test_medicao_abre_nota_principal_sem_origem_marcada_e_com_valor_bloqueado(self):
        contrato = self.criar_contrato(numero='107-X/2026', prazo=1)
        item = self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response_medicao = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{item.pk}': '2.00'},
        )
        self.assertEqual(response_medicao.status_code, 302)

        response = self.client.get(reverse('contratos:competencia_medicao', args=[competencia.pk]))
        form = response.context['form']

        self.assertIsNone(form.fields['origem_valor_nota_fiscal'].initial)
        self.assertEqual(form.fields['valor_nota_fiscal'].widget.attrs.get('readonly'), 'readonly')

    def test_medicao_expoe_valor_medido_em_formato_compativel_com_input_number_no_javascript(self):
        contrato = self.criar_contrato(numero='107-Y/2026', prazo=1)
        item = self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response_medicao = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{item.pk}': '2.00'},
        )
        self.assertEqual(response_medicao.status_code, 302)

        response = self.client.get(reverse('contratos:competencia_medicao', args=[competencia.pk]))
        self.assertContains(response, "const valorMedicaoReferencia = '100.00';")

    def test_medicao_permite_usar_valor_medido_como_valor_da_nota_fiscal(self):
        contrato = self.criar_contrato(numero='107-A/2026', prazo=1)
        item = self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response_medicao = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{item.pk}': '2.00'},
        )
        self.assertEqual(response_medicao.status_code, 302)

        response_nota = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {'origem_valor_nota_fiscal': 'medicao'},
        )
        self.assertEqual(response_nota.status_code, 302)

        competencia.refresh_from_db()
        self.assertEqual(competencia.valor_medido, Decimal('100.00'))
        self.assertEqual(competencia.valor_nota_fiscal, Decimal('100.00'))

    def test_medicao_recalcula_valor_a_pagar_com_retentoes_ao_usar_valor_medido(self):
        contrato = self.criar_contrato(numero='107-B/2026', prazo=1)
        item = self.criar_item_contrato(contrato, quantidade='3.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response_medicao = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{item.pk}': '3.00'},
        )
        self.assertEqual(response_medicao.status_code, 302)

        response_nota = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {
                'origem_valor_nota_fiscal': 'medicao',
                'retencao_ir': '10.00',
                'retencao_inss': '5.00',
                'retencao_iss': '2.00',
            },
        )
        self.assertEqual(response_nota.status_code, 302)

        competencia.refresh_from_db()
        self.assertEqual(competencia.valor_medido, Decimal('150.00'))
        self.assertEqual(competencia.valor_nota_fiscal, Decimal('150.00'))
        self.assertEqual(competencia.valor_liberado_final, Decimal('133.00'))

    def test_medicao_impede_salvar_nota_principal_antes_da_medicao(self):
        contrato = self.criar_contrato(numero='108/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {
                'numero_nota_fiscal': 'NF-001',
                'valor_nota_fiscal': '100.00',
            },
        )
        competencia.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Salve a etapa de medição antes de preencher a nota fiscal principal.')
        self.assertEqual(competencia.numero_nota_fiscal, '')
        self.assertEqual(competencia.valor_nota_fiscal, Decimal('0.00'))

    def test_medicao_impede_salvar_nota_adicional_antes_da_nota_principal(self):
        contrato = self.criar_contrato(numero='109/2026', prazo=1)
        item = self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()

        self.client.login(username='gestor_v2', password='123')
        response_medicao = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {f'quantidade_{item.pk}': '2.00'},
        )
        self.assertEqual(response_medicao.status_code, 302)

        response = self.client.post(
            reverse('contratos:competencia_medicao', args=[competencia.pk]),
            {
                'numero_nota_adicional': 'NFA-001',
                'valor_nota_adicional': '10.00',
            },
        )
        competencia.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Salve a medição e a nota fiscal principal antes de preencher a nota fiscal adicional.')
        self.assertEqual(competencia.numero_nota_adicional, '')
        self.assertEqual(competencia.valor_nota_adicional, Decimal('0.00'))

    def test_auditoria_da_avaliacao_gera_evento_da_competencia(self):
        contrato = self.criar_contrato(numero='106/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='2.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        self.criar_formulario_avaliacao(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.medicao_concluida_em = timezone.now()
        competencia.status = CompetenciaPagamento.Status.AVALIACAO_PENDENTE
        competencia.save(update_fields=['medicao_concluida_em', 'status', 'atualizado_em'])

        self.client.login(username='gestor_v2', password='123')
        resposta = competencia.avaliacao_qualidade.itens.get()

        response = self.client.post(
            reverse('contratos:competencia_avaliacao', args=[competencia.pk]),
            {
                f'nota_fiscal_{resposta.pk}': '1.00',
                f'justificativa_fiscal_{resposta.pk}': 'Entrega parcial no período.',
                'observacoes': 'Avaliação auditada',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CompetenciaAuditoriaEvento.objects.filter(
                competencia=competencia,
                tipo_evento=CompetenciaAuditoriaEvento.TipoEvento.AVALIACAO_ATUALIZADA,
            ).exists()
        )

    def test_auditoria_da_ob_gera_evento_da_competencia(self):
        contrato = self.criar_contrato(numero='107/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        competencia.status = CompetenciaPagamento.Status.OB_PENDENTE
        competencia.valor_liberado_final = Decimal('50.00')
        competencia.save(update_fields=['status', 'valor_liberado_final', 'atualizado_em'])

        self.client.login(username='gestor_v2', password='123')
        response = self.client.post(
            reverse('contratos:competencia_ob', args=[competencia.pk]),
            {
                'ordem_bancaria_arquivo': SimpleUploadedFile('ob.pdf', pdf_minimo_valido(), content_type='application/pdf'),
                'data_pagamento': '2026-01-31',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            CompetenciaAuditoriaEvento.objects.filter(
                competencia=competencia,
                tipo_evento=CompetenciaAuditoriaEvento.TipoEvento.OB_EXECUTADA,
            ).exists()
        )

    def test_detalhe_do_contrato_exibe_status_visivel_da_exportacao_recente(self):
        contrato = self.criar_contrato(numero='107-A/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        ExportacaoDocumentosCompetencia.objects.create(
            competencia=competencia,
            solicitado_por=self.gestor,
            status=ExportacaoDocumentosCompetencia.Status.PROCESSANDO,
            etapa_atual='Gerando checklist',
            percentual=50,
            mensagem='Preparando a capa do checklist e reunindo os documentos anexados.',
            tipo_saida='unificado',
        )

        self.client.login(username='gestor_v2', password='123')
        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Geração de documentos')
        self.assertContains(response, 'Gerando checklist')
        self.assertContains(response, '50%')
        self.assertContains(response, 'Processando')

    def test_status_da_exportacao_retorna_metadados_para_feedback_inline(self):
        contrato = self.criar_contrato(numero='107-B/2026', prazo=1)
        self.criar_item_contrato(contrato, quantidade='1.00', unitario='50.00')
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        job = ExportacaoDocumentosCompetencia.objects.create(
            competencia=competencia,
            solicitado_por=self.gestor,
            status=ExportacaoDocumentosCompetencia.Status.PENDENTE,
            etapa_atual='Na fila',
            percentual=0,
            mensagem='A exportação foi criada e será iniciada em instantes.',
            tipo_saida='separado',
        )

        self.client.login(username='gestor_v2', password='123')
        response = self.client.get(reverse('contratos:competencia_download_docs_status', args=[job.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['job_id'], job.pk)
        self.assertEqual(payload['competencia_id'], competencia.pk)
        self.assertEqual(payload['status_display'], 'Pendente')
        self.assertEqual(payload['tipo_saida'], 'separado')

    def test_detalhe_do_contrato_renderiza_historicos_inline(self):
        contrato = self.criar_contrato(numero='108/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        ContratoAuditoriaEvento.objects.create(
            contrato=contrato,
            tipo_evento=ContratoAuditoriaEvento.TipoEvento.CONTRATO_CRIADO,
            usuario=self.gestor,
            resumo='criou o contrato',
            payload={},
        )
        CompetenciaAuditoriaEvento.objects.create(
            competencia=competencia,
            tipo_evento=CompetenciaAuditoriaEvento.TipoEvento.COMPETENCIA_CRIADA,
            usuario=self.gestor,
            resumo='criou a competência',
            payload={},
        )

        self.client.login(username='gestor_v2', password='123')
        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Histórico do contrato')
        self.assertContains(response, 'Histórico da competência')

    def test_detalhe_do_contrato_formata_payload_extra_da_auditoria(self):
        contrato = self.criar_contrato(numero='108-A/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        competencia = contrato.competencias.get()
        CompetenciaAuditoriaEvento.objects.create(
            competencia=competencia,
            tipo_evento=CompetenciaAuditoriaEvento.TipoEvento.MEDICAO_ATUALIZADA,
            usuario=self.gestor,
            resumo='atualizou a medição',
            payload={
                'extra': {
                    'secoes_alteradas': ['aceite_provisorio'],
                    'medicoes_alteradas': [
                        {'item': 'Adicional de BI Pro', 'antes': '0.00', 'depois': '24.00'},
                        {'item': 'BÁSICO E1', 'antes': '0.00', 'depois': '50.00'},
                    ],
                }
            },
        )

        self.client.login(username='gestor_v2', password='123')
        response = self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertContains(response, 'Seções alteradas')
        self.assertContains(response, 'Aceite provisório')
        self.assertContains(response, 'Medições alteradas')
        self.assertContains(response, 'Adicional de BI Pro: 0.00 -&gt; 24.00')
        self.assertContains(response, 'BÁSICO E1: 0.00 -&gt; 50.00')

    def test_get_do_detalhe_nao_cria_eventos_de_auditoria(self):
        contrato = self.criar_contrato(numero='109/2026', prazo=1)
        self.criar_item_contrato(contrato)
        self.criar_checklist_ativo(contrato)
        contrato.gerar_competencias()
        self.client.login(username='gestor_v2', password='123')

        self.client.get(reverse('contratos:contrato_detail', args=[contrato.pk]))

        self.assertFalse(ContratoAuditoriaEvento.objects.filter(contrato=contrato).exists())
        self.assertFalse(CompetenciaAuditoriaEvento.objects.filter(competencia__contrato=contrato).exists())
