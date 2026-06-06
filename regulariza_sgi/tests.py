# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Validar cadastro, CADIN, timeline, ciclos, anexos e busca do Regulariza SGI.

import shutil
import tempfile
from datetime import date
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ImovelForm
from .models import CicloProcessual, Imovel
from .services import compute_timeline_context, current_cycle, sync_ciclo


User = get_user_model()


def arquivo_teste():
    """Cria arquivo simples para simular upload de anexo."""

    return SimpleUploadedFile('anexo.txt', b'conteudo de teste', content_type='text/plain')


class RegularizaSgiTests(TestCase):
    """Cobre regras cadastrais, cálculos processuais e telas principais do módulo."""

    def setUp(self):
        # Isola uploads em diretório temporário e autentica usuário administrativo.
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = User.objects.create_superuser(username='admin_regulariza', password='123', email='admin@example.com')
        self.client.login(username='admin_regulariza', password='123')

    def tearDown(self):
        # Remove arquivos temporários mesmo quando algum teste falha.
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def criar_imovel(self, **kwargs):
        """Cria imóvel válido com valores padrão para os testes."""

        defaults = {
            'inscricao_imobiliaria': '123.456.789',
            'matricula': 'MAT-001',
            'processo_judicial': '0001/2026',
            'numero_sgi': 'SGI-100',
            'uf': 'SP',
            'municipio': 'São Paulo',
            'logradouro': 'Rua das Flores',
            'bairro': 'Centro',
            'numero': '100',
            'area': '1250.50',
            'possui_cadin': False,
            'exercicio_cadin': '',
            'notificacao_cadin_municipal': '',
        }
        defaults.update(kwargs)
        return Imovel.objects.create(**defaults)

    def test_cadastro_de_imovel_exige_inscricao_unica(self):
        self.criar_imovel()
        form = ImovelForm(
            data={
                'inscricao_imobiliaria': '123.456.789',
                'matricula': 'MAT-002',
                'processo_judicial': '0002/2026',
                'numero_sgi': 'SGI-200',
                'uf': 'SP',
                'municipio': 'São Paulo',
                'logradouro': 'Rua B',
                'bairro': 'Bela Vista',
                'numero': '20',
                'area': '90.00',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('inscricao_imobiliaria', form.errors)

    def test_regra_de_cadin_salva_e_limpa_campo_corretamente(self):
        form = ImovelForm(
            data={
                'inscricao_imobiliaria': '999.888.777',
                'matricula': 'MAT-003',
                'processo_judicial': '0003/2026',
                'numero_sgi': 'SGI-300',
                'uf': 'SP',
                'municipio': 'São Paulo',
                'logradouro': 'Rua C',
                'bairro': 'Consolação',
                'numero': 'S/N',
                'area': '45.00',
                'possui_cadin': 'on',
                'exercicio_cadin': '2023',
                'notificacao_cadin_municipal': 'CADIN-SP-001',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        imovel = form.save()
        self.assertEqual(imovel.exercicio_cadin, '2023')
        self.assertEqual(imovel.notificacao_cadin_municipal, 'CADIN-SP-001')

        form = ImovelForm(
            data={
                'inscricao_imobiliaria': imovel.inscricao_imobiliaria,
                'matricula': imovel.matricula,
                'processo_judicial': imovel.processo_judicial,
                'numero_sgi': imovel.numero_sgi,
                'uf': imovel.uf,
                'municipio': imovel.municipio,
                'logradouro': imovel.logradouro,
                'bairro': imovel.bairro,
                'numero': imovel.numero,
                'area': imovel.area,
                'exercicio_cadin': '2023',
                'notificacao_cadin_municipal': 'CADIN-SP-001',
            },
            instance=imovel,
        )

        self.assertTrue(form.is_valid(), form.errors)
        atualizado = form.save()
        self.assertEqual(atualizado.exercicio_cadin, '')
        self.assertEqual(atualizado.notificacao_cadin_municipal, '')

    def test_cria_marco_inicial_automaticamente_ao_criar_imovel(self):
        imovel = self.criar_imovel()
        ciclo = current_cycle(imovel)

        self.assertIsNotNone(ciclo)
        self.assertEqual(ciclo.numero, 1)
        self.assertEqual(ciclo.marcos.first().titulo, 'Cadastro do Imóvel')
        self.assertEqual(ciclo.marcos.first().usuario_responsavel, 'Sistema')

    def test_area_pode_ser_omitida_no_formulario(self):
        form = ImovelForm(
            data={
                'inscricao_imobiliaria': '555.444.333',
                'matricula': 'MAT-004',
                'processo_judicial': '0004/2026',
                'numero_sgi': 'SGI-400',
                'uf': 'SP',
                'municipio': 'São Paulo',
                'logradouro': 'Rua D',
                'bairro': 'Sé',
                'numero': '50',
                'area': '',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        imovel = form.save()
        self.assertIsNone(imovel.area)

    def test_protocolo_gera_manifestacao_prevista_correta(self):
        imovel = self.criar_imovel()
        ciclo = current_cycle(imovel)
        ciclo.numero_protocolo = 'PROTO-1'
        ciclo.data_protocolo = date(2026, 3, 1)
        ciclo.prazo_resposta_dias = 120
        sync_ciclo(ciclo)

        self.assertEqual(ciclo.data_manifestacao_prevista.isoformat(), '2026-06-29')

    def test_prorrogacao_altera_data_prevista_da_manifestacao(self):
        imovel = self.criar_imovel()
        ciclo = current_cycle(imovel)
        ciclo.numero_protocolo = 'PROTO-2'
        ciclo.data_protocolo = date(2026, 3, 1)
        ciclo.prazo_resposta_dias = 30
        ciclo.prorrogacao_dias = 15
        ciclo.data_prorrogacao = date(2026, 3, 20)
        sync_ciclo(ciclo)

        self.assertEqual(ciclo.data_manifestacao_prevista.isoformat(), '2026-04-15')

    def test_deferimento_gera_vencimento_e_renovacao(self):
        imovel = self.criar_imovel(
            possui_cadin=True,
            exercicio_cadin='2023',
            notificacao_cadin_municipal='CADIN-SP-2023',
        )
        ciclo = current_cycle(imovel)
        ciclo.numero_protocolo = 'PROTO-3'
        ciclo.data_protocolo = date(2026, 3, 1)
        ciclo.prazo_resposta_dias = 30
        ciclo.resultado = CicloProcessual.Resultado.DEFERIDO
        ciclo.data_manifestacao = date(2026, 4, 1)
        ciclo.prazo_imunidade_anos = 5
        sync_ciclo(ciclo)
        imovel.refresh_from_db()

        self.assertEqual(ciclo.data_vencimento_imunidade.isoformat(), '2031-04-01')
        self.assertEqual(ciclo.data_renovacao_prevista.isoformat(), '2030-10-03')
        self.assertFalse(imovel.possui_cadin_ativo)

    def test_indeferimento_gera_prazo_contrarrazao_e_novo_ciclo(self):
        imovel = self.criar_imovel()
        ciclo = current_cycle(imovel)
        ciclo.numero_protocolo = 'PROTO-4'
        ciclo.data_protocolo = date(2026, 4, 1)
        ciclo.prazo_resposta_dias = 10
        ciclo.resultado = CicloProcessual.Resultado.INDEFERIDO
        ciclo.data_manifestacao = date(2026, 4, 20)
        sync_ciclo(ciclo)

        self.assertEqual(ciclo.data_contrarrazao_limite.isoformat(), '2026-04-23')

        response = self.client.post(reverse('regulariza_sgi:reinicio_ciclo', args=[imovel.pk]))

        self.assertRedirects(response, reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), fetch_redirect_response=False)
        self.assertEqual(imovel.ciclos.count(), 2)
        self.assertEqual(current_cycle(imovel).tipo, CicloProcessual.Tipo.CONTRARRAZAO)

    def test_calculo_de_cores_da_timeline_nas_faixas(self):
        verde = self.criar_imovel(inscricao_imobiliaria='111')
        amarelo = self.criar_imovel(inscricao_imobiliaria='222')
        vermelho = self.criar_imovel(inscricao_imobiliaria='333')
        # Em um prazo de 30 dias: 50% permanece verde, 60% é amarelo e acima de 75% é vermelho.
        for imovel, days_ago in ((verde, 15), (amarelo, 18), (vermelho, 23)):
            created_at = timezone.now() - timedelta(days=days_ago)
            local_start_date = timezone.localdate() - timedelta(days=days_ago)
            Imovel.objects.filter(pk=imovel.pk).update(criado_em=created_at)
            ciclo = current_cycle(imovel)
            CicloProcessual.objects.filter(pk=ciclo.pk).update(data_inicio=local_start_date)
        verde.refresh_from_db()
        amarelo.refresh_from_db()
        vermelho.refresh_from_db()

        self.assertEqual(compute_timeline_context(verde)['color'], 'verde')
        self.assertEqual(compute_timeline_context(amarelo)['color'], 'amarelo')
        self.assertEqual(compute_timeline_context(vermelho)['color'], 'vermelho')

    def test_listagem_renderiza_indicador_de_cadin(self):
        imovel = self.criar_imovel(
            possui_cadin=True,
            exercicio_cadin='2017 à 2023',
            notificacao_cadin_municipal='CADIN-SP-2017-2023',
        )

        response = self.client.get(reverse('regulariza_sgi:imovel_list'))

        self.assertContains(response, imovel.inscricao_imobiliaria)
        self.assertContains(response, 'CADIN 2017 à 2023')
        self.assertContains(response, 'regulariza-cadin-triangle')

    def test_detalhe_permite_enviar_anexo(self):
        imovel = self.criar_imovel()

        response = self.client.post(
            reverse('regulariza_sgi:anexo_create', args=[imovel.pk]),
            {'nome_exibicao': 'Matrícula', 'arquivo': arquivo_teste()},
        )

        self.assertRedirects(response, reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), fetch_redirect_response=False)
        self.assertEqual(imovel.anexos.count(), 1)

    def test_listagem_pesquisa_por_qualquer_item_do_cadastro(self):
        alvo = self.criar_imovel(
            inscricao_imobiliaria='197.033.0003-1',
            matricula='MAT-SANTA',
            processo_judicial='PROC-AGUA-BRANCA',
            numero_sgi='SGI-AGUA',
            municipio='São Paulo',
            logradouro='Av. Santa Marina',
            bairro='Água Branca',
            numero='416',
            exercicio_cadin='2024',
            notificacao_cadin_municipal='CADIN-416',
        )
        self.criar_imovel(
            inscricao_imobiliaria='000.000.0001-0',
            matricula='OUTRA',
            processo_judicial='PROC-OUTRO',
            numero_sgi='SGI-OUTRO',
            municipio='Campinas',
            logradouro='Rua Teste',
            bairro='Centro',
            numero='10',
        )

        response = self.client.get(reverse('regulariza_sgi:imovel_list'), {'q': 'Água Branca'})

        self.assertContains(response, alvo.inscricao_imobiliaria)
        self.assertNotContains(response, '000.000.0001-0')

    def test_timeline_destaca_trecho_entre_marco_atual_e_proximo(self):
        imovel = self.criar_imovel()

        context = compute_timeline_context(imovel)

        self.assertEqual(context['marco_atual'].titulo, 'Cadastro do Imóvel')
        self.assertEqual(context['proximo_marco'].titulo, 'Protocolo')
        self.assertEqual(context['prazo_total_dias'], 30)

    def test_historico_registra_usuario_que_fez_o_protocolo(self):
        imovel = self.criar_imovel()

        response = self.client.post(
            reverse('regulariza_sgi:protocolo_create', args=[imovel.pk]),
            {
                'numero_protocolo': 'PROTO-TESTE',
                'data_protocolo': '2026-06-10',
                'prazo_resposta_dias': '30',
            },
        )

        self.assertRedirects(response, reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), fetch_redirect_response=False)
        ciclo = current_cycle(imovel)
        marco = ciclo.marcos.get(tipo='PROTOCOLO')
        self.assertEqual(marco.usuario_responsavel, 'admin_regulariza')

        detail_response = self.client.get(reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]))
        self.assertContains(detail_response, 'Histórico')
        self.assertContains(detail_response, 'admin_regulariza')
