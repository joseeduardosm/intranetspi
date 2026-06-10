# Criado por José Eduardo Santana Martins em 04/06/2026
# Atualizado por Codex em 09/06/2026
# Objetivo: Validar cadastro em abas, fluxo processual, observações e timeline do Regulariza SGI.

import shutil
import tempfile
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import ImovelForm
from .models import CicloProcessual, Imovel, ImovelObservacao, ImovelTimelineEvento
from .services import compute_timeline_context, current_cycle, sync_ciclo


User = get_user_model()


def arquivo_teste():
    """Cria arquivo simples para simular upload de anexo."""

    return SimpleUploadedFile('anexo.txt', b'conteudo de teste', content_type='text/plain')


class RegularizaSgiTests(TestCase):
    """Cobre o novo desenho cadastral e o histórico consolidado do módulo."""

    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = User.objects.create_superuser(username='admin_regulariza', password='123', email='admin@example.com')
        self.client.login(username='admin_regulariza', password='123')

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def criar_imovel(self, **kwargs):
        """Cria imóvel válido com defaults alinhados ao novo cadastro."""

        defaults = {
            'inscricao_imobiliaria': '123.456.789',
            'matricula': 'MAT-001',
            'processo_judicial': '0001/2026',
            'sei': 'SEI-001',
            'link_sei': 'https://sei.exemplo/001',
            'numero_sgi': 'SGI-100',
            'uf': 'SP',
            'municipio': 'São Paulo',
            'logradouro': 'Rua das Flores',
            'bairro': 'Centro',
            'numero': '100',
            'area': '1250.50',
            'imunidade': False,
            'tempo_imunidade': None,
            'possui_cadin': False,
            'exercicio_cadin': '',
            'notificacao_cadin_municipal': '',
        }
        defaults.update(kwargs)
        return Imovel.objects.create(**defaults)

    def test_formulario_padrao_usa_sp_e_sao_paulo(self):
        form = ImovelForm()

        self.assertEqual(form.fields['uf'].initial, 'SP')
        self.assertEqual(form.fields['municipio'].initial, 'São Paulo')

    def test_cadastro_sem_imunidade_salva_normalmente(self):
        form = ImovelForm(
            data={
                'inscricao_imobiliaria': '999.888.777',
                'matricula': 'MAT-003',
                'sei': 'SEI-003',
                'link_sei': 'https://sei.exemplo/003',
                'logradouro': 'Rua C',
                'uf': 'SP',
                'municipio': 'São Paulo',
                'bairro': 'Consolação',
                'area': '45.00',
                'processo_judicial': '0003/2026',
                'imissao_posse': '',
                'imunidade': 'nao',
                'tempo_imunidade': '',
                'exercicio_cobranca': '',
                'divida_ativa': '',
                'numero_divida': '',
                'dividas_nao_ajuizadas': '',
                'dividas_ajuizadas': '',
                'encargos': '',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        imovel = form.save()
        self.assertFalse(imovel.imunidade)
        self.assertIsNone(imovel.tempo_imunidade)

    def test_campos_monetarios_aceitam_formato_brasileiro_e_salvam_como_decimal(self):
        form = ImovelForm(
            data={
                'inscricao_imobiliaria': '555.444.333',
                'matricula': 'MAT-006',
                'sei': '',
                'link_sei': '',
                'logradouro': 'Rua Monetaria',
                'uf': 'SP',
                'municipio': 'São Paulo',
                'bairro': 'Centro',
                'area': '',
                'processo_judicial': '0006/2026',
                'imissao_posse': '',
                'imunidade': 'nao',
                'tempo_imunidade': '',
                'exercicio_cobranca': '',
                'divida_ativa': '',
                'numero_divida': '',
                'dividas_nao_ajuizadas': '2.123,32',
                'dividas_ajuizadas': '15.020,40',
                'encargos': '99,90',
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        imovel = form.save()
        self.assertEqual(str(imovel.dividas_nao_ajuizadas), '2123.32')
        self.assertEqual(str(imovel.dividas_ajuizadas), '15020.40')
        self.assertEqual(str(imovel.encargos), '99.90')

    def test_cadastro_com_imunidade_exige_tempo_e_salva(self):
        form_invalido = ImovelForm(
            data={
                'inscricao_imobiliaria': '111.222.333',
                'matricula': 'MAT-004',
                'sei': 'SEI-004',
                'link_sei': 'https://sei.exemplo/004',
                'logradouro': 'Rua D',
                'uf': 'SP',
                'municipio': 'São Paulo',
                'bairro': 'Sé',
                'area': '90.00',
                'processo_judicial': '0004/2026',
                'imissao_posse': '2026-01-05',
                'imunidade': 'sim',
                'tempo_imunidade': '',
            }
        )
        form_valido = ImovelForm(
            data={
                'inscricao_imobiliaria': '111.222.334',
                'matricula': 'MAT-005',
                'sei': 'SEI-005',
                'link_sei': 'https://sei.exemplo/005',
                'logradouro': 'Rua E',
                'uf': 'SP',
                'municipio': 'São Paulo',
                'bairro': 'Sé',
                'area': '91.00',
                'processo_judicial': '0005/2026',
                'imissao_posse': '2026-01-06',
                'imunidade': 'sim',
                'tempo_imunidade': '5',
            }
        )

        self.assertFalse(form_invalido.is_valid())
        self.assertIn('tempo_imunidade', form_invalido.errors)
        self.assertTrue(form_valido.is_valid(), form_valido.errors)
        imovel = form_valido.save()
        self.assertTrue(imovel.imunidade)
        self.assertEqual(imovel.tempo_imunidade, 5)

    def test_cria_ciclo_e_evento_de_cadastro_automaticamente(self):
        imovel = self.criar_imovel()
        ciclo = current_cycle(imovel)

        self.assertIsNotNone(ciclo)
        self.assertEqual(ciclo.numero, 1)
        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.CADASTRO).exists())

    def test_listagem_pesquisa_permanece_com_campos_originais(self):
        alvo = self.criar_imovel(
            inscricao_imobiliaria='197.033.0003-1',
            matricula='MAT-SANTA',
            processo_judicial='PROC-AGUA-BRANCA',
            sei='SEI-AGUA',
            link_sei='https://sei.exemplo/agua',
            logradouro='Av. Santa Marina',
            bairro='Água Branca',
            exercicio_cobranca='2024',
            divida_ativa='DA-416',
        )
        self.criar_imovel(
            inscricao_imobiliaria='000.000.0001-0',
            matricula='OUTRA',
            processo_judicial='PROC-OUTRO',
            sei='SEI-OUTRO',
            link_sei='https://sei.exemplo/outro',
            municipio='Campinas',
            logradouro='Rua Teste',
            bairro='Centro',
        )

        response = self.client.get(reverse('regulariza_sgi:imovel_list'), {'q': 'Água Branca'})

        self.assertContains(response, alvo.inscricao_imobiliaria)
        self.assertNotContains(response, '000.000.0001-0')

    def test_detalhe_exibe_prorrogacao_e_manifestacao_apos_protocolo(self):
        imovel = self.criar_imovel()

        self.client.post(
            reverse('regulariza_sgi:protocolo_create', args=[imovel.pk]),
            {
                'numero_protocolo': 'PROTO-TESTE',
                'data_protocolo': '2026-06-10',
                'prazo_resposta_dias': '30',
            },
        )
        response = self.client.get(reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]))

        self.assertContains(response, 'Salvar prorrogação')
        self.assertContains(response, 'Salvar manifestação')

    def test_manifestacao_pode_ocorrer_sem_prorrogacao(self):
        imovel = self.criar_imovel()
        ciclo = current_cycle(imovel)
        ciclo.numero_protocolo = 'PROTO-1'
        ciclo.data_protocolo = date(2026, 3, 1)
        ciclo.prazo_resposta_dias = 30
        sync_ciclo(ciclo)

        response = self.client.post(
            reverse('regulariza_sgi:manifestacao_create', args=[imovel.pk]),
            {
                'resultado': CicloProcessual.Resultado.DEFERIDO,
                'data_manifestacao': '2026-03-20',
                'prazo_imunidade_anos': '5',
            },
        )
        imovel.refresh_from_db()
        ciclo.refresh_from_db()

        self.assertRedirects(response, reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), fetch_redirect_response=False)
        self.assertEqual(ciclo.resultado, CicloProcessual.Resultado.DEFERIDO)
        self.assertTrue(imovel.imunidade)
        self.assertEqual(imovel.tempo_imunidade, 5)

    def test_observacoes_sao_registradas_com_usuario_e_paginadas(self):
        imovel = self.criar_imovel()
        for indice in range(11):
            ImovelObservacao.objects.create(
                imovel=imovel,
                texto=f'Observação {indice}',
                usuario_responsavel='admin_regulariza',
            )

        response = self.client.get(reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), {'aba': 'observacoes', 'subaba': 'observacoes'})

        self.assertContains(response, 'Observação 10')
        self.assertNotContains(response, 'Observação 0')
        self.assertContains(response, 'Página 1 de 2')

    def test_criar_observacao_inline_registra_timeline(self):
        imovel = self.criar_imovel()

        response = self.client.post(
            reverse('regulariza_sgi:observacao_create', args=[imovel.pk]),
            {'texto': 'Nova observação operacional.'},
        )

        self.assertRedirects(
            response,
            f"{reverse('regulariza_sgi:imovel_detail', args=[imovel.pk])}?aba=observacoes&subaba=observacoes",
            fetch_redirect_response=False,
        )
        self.assertEqual(imovel.observacoes.count(), 1)
        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.OBSERVACAO).exists())

    def test_timeline_registra_eventos_de_sei_anexo_e_fluxo(self):
        imovel = self.criar_imovel()

        self.client.post(
            reverse('regulariza_sgi:sei_create', args=[imovel.pk]),
            {'numero_sei': 'SEI-EXTRA', 'link_sei': 'https://sei.exemplo/extra'},
        )
        self.client.post(
            reverse('regulariza_sgi:anexo_create', args=[imovel.pk]),
            {'nome_exibicao': 'Matrícula', 'arquivo': arquivo_teste()},
        )
        self.client.post(
            reverse('regulariza_sgi:protocolo_create', args=[imovel.pk]),
            {'numero_protocolo': 'PROTO-9', 'data_protocolo': '2026-06-10', 'prazo_resposta_dias': '30'},
        )
        self.client.post(
            reverse('regulariza_sgi:prorrogacao_create', args=[imovel.pk]),
            {'prorrogacao_dias': '10', 'data_prorrogacao': '2026-06-20'},
        )
        self.client.post(
            reverse('regulariza_sgi:manifestacao_create', args=[imovel.pk]),
            {
                'resultado': CicloProcessual.Resultado.INDEFERIDO,
                'data_manifestacao': '2026-06-25',
                'prazo_imunidade_anos': '',
            },
        )
        response = self.client.get(reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), {'aba': 'observacoes', 'subaba': 'timeline'})

        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.PROCESSO_SEI).exists())
        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.ANEXO).exists())
        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.PROTOCOLO).exists())
        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.PRORROGACAO).exists())
        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.MANIFESTACAO).exists())
        self.assertContains(response, 'Processo SEI')
        self.assertContains(response, 'Prorrogação')

    def test_edicao_de_imovel_existente_salva_com_sucesso(self):
        imovel = self.criar_imovel(
            inscricao_imobiliaria='076.308.0057-6',
            matricula='MAT-EDIT',
            municipio='Araraquara',
            logradouro='Rua Original',
            bairro='Centro',
            possui_cadin=True,
            exercicio_cadin='2016 a 2025',
            notificacao_cadin_municipal='000',
        )

        response = self.client.post(
            reverse('regulariza_sgi:imovel_update', args=[imovel.pk]),
            {
                'inscricao_imobiliaria': imovel.inscricao_imobiliaria,
                'matricula': imovel.matricula,
                'sei': imovel.sei,
                'link_sei': imovel.link_sei,
                'logradouro': 'Rua Alterada',
                'uf': imovel.uf,
                'municipio': imovel.municipio,
                'bairro': imovel.bairro,
                'area': imovel.area,
                'processo_judicial': imovel.processo_judicial,
                'imissao_posse': '',
                'imunidade': 'nao',
                'tempo_imunidade': '',
                'exercicio_cobranca': '',
                'divida_ativa': '',
                'numero_divida': '',
                'dividas_nao_ajuizadas': '',
                'dividas_ajuizadas': '',
                'encargos': '',
            },
        )
        imovel.refresh_from_db()

        self.assertRedirects(response, reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), fetch_redirect_response=False)
        self.assertEqual(imovel.logradouro, 'Rua Alterada')

    def test_reinicio_de_ciclo_registra_timeline(self):
        imovel = self.criar_imovel()
        ciclo = current_cycle(imovel)
        ciclo.numero_protocolo = 'PROTO-4'
        ciclo.data_protocolo = date(2026, 4, 1)
        ciclo.prazo_resposta_dias = 10
        ciclo.resultado = CicloProcessual.Resultado.INDEFERIDO
        ciclo.data_manifestacao = date(2026, 4, 20)
        sync_ciclo(ciclo)

        response = self.client.post(reverse('regulariza_sgi:reinicio_ciclo', args=[imovel.pk]))

        self.assertRedirects(response, reverse('regulariza_sgi:imovel_detail', args=[imovel.pk]), fetch_redirect_response=False)
        self.assertEqual(imovel.ciclos.count(), 2)
        self.assertTrue(imovel.timeline_eventos.filter(tipo=ImovelTimelineEvento.Tipo.CICLO).exists())

    def test_timeline_processual_atual_permanece_funcional(self):
        verde = self.criar_imovel(inscricao_imobiliaria='111')
        amarelo = self.criar_imovel(inscricao_imobiliaria='222')
        vermelho = self.criar_imovel(inscricao_imobiliaria='333')
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
