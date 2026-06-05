# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Validar publicação, anexos, listagens públicas e gestão editorial.

import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from atalhos.models import Atalho

from .forms import NoticiaForm
from .models import Noticia


def imagem_teste():
    """Cria uma imagem mínima para simular upload nos testes."""

    return SimpleUploadedFile(
        'destaque.gif',
        b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;',
        content_type='image/gif',
    )


def pdf_teste(nome='orientacoes.pdf'):
    """Cria um PDF mínimo para validar anexo incorporado."""

    return SimpleUploadedFile(
        nome,
        b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF',
        content_type='application/pdf',
    )


def arquivo_teste(nome='planilha.xlsx'):
    """Cria um anexo genérico que deve ser oferecido para download."""

    return SimpleUploadedFile(
        nome,
        b'arquivo teste',
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


class NoticiasTests(TestCase):
    """Cobre regras editoriais, exibição pública, anexos e comandos de publicação."""

    def setUp(self):
        # Isola arquivos enviados em diretório temporário durante os testes.
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        # Remove os arquivos temporários mesmo se algum teste falhar.
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def criar_noticia(self, **kwargs):
        """Cria uma notícia publicada com valores padrão úteis para os testes."""

        defaults = {
            'imagem_destaque': 'noticias/destaques/teste.jpg',
            'titulo': 'Noticia publicada',
            'texto_noticia': 'Texto completo.',
            'status': Noticia.Status.PUBLICADA,
            'data_publicacao': timezone.now() - timedelta(hours=1),
        }
        defaults.update(kwargs)
        return Noticia.objects.create(**defaults)

    def test_rascunho_pode_ficar_sem_data_publicacao(self):
        noticia = Noticia(
            imagem_destaque='noticias/destaques/teste.jpg',
            titulo='Rascunho',
            texto_noticia='Texto.',
            status=Noticia.Status.RASCUNHO,
        )

        noticia.full_clean()

    def test_agendada_ou_publicada_exige_data_publicacao(self):
        noticia = Noticia(
            imagem_destaque='noticias/destaques/teste.jpg',
            titulo='Agendada',
            texto_noticia='Texto.',
            status=Noticia.Status.AGENDADA,
        )

        with self.assertRaises(ValidationError):
            noticia.full_clean()

    def test_form_aceita_noticia_agendada_com_data_futura(self):
        form = NoticiaForm(
            data={
                'titulo': 'Agendada',
                'texto_noticia': 'Texto.',
                'status': Noticia.Status.AGENDADA,
                'data_publicacao': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
                'fixada': 'on',
            },
            files={'imagem_destaque': imagem_teste()},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_aceita_pdf_anexo(self):
        form = NoticiaForm(
            data={
                'titulo': 'Com PDF',
                'texto_noticia': 'Texto.',
                'status': Noticia.Status.RASCUNHO,
            },
            files={'imagem_destaque': imagem_teste(), 'anexo_pdf': pdf_teste()},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_aceita_anexo_que_nao_e_pdf(self):
        form = NoticiaForm(
            data={
                'titulo': 'Com anexo',
                'texto_noticia': 'Texto.',
                'status': Noticia.Status.RASCUNHO,
            },
            files={
                'imagem_destaque': imagem_teste(),
                'anexo_pdf': arquivo_teste(),
            },
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_listagem_publica_exibe_somente_publicadas_vencidas(self):
        publicada = self.criar_noticia(titulo='Publicada agora')
        self.criar_noticia(titulo='Rascunho', status=Noticia.Status.RASCUNHO, data_publicacao=None)
        self.criar_noticia(
            titulo='Agendada futura',
            status=Noticia.Status.AGENDADA,
            data_publicacao=timezone.now() + timedelta(days=1),
        )
        self.criar_noticia(
            titulo='Publicada futura',
            status=Noticia.Status.PUBLICADA,
            data_publicacao=timezone.now() + timedelta(days=1),
        )

        response = self.client.get(reverse('noticias:public_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, publicada.titulo)
        self.assertNotContains(response, 'Rascunho')
        self.assertNotContains(response, 'Agendada futura')
        self.assertNotContains(response, 'Publicada futura')

    def test_home_distribui_noticias_nos_slots_do_layout(self):
        noticias = [
            self.criar_noticia(
                titulo=f'Noticia {idx}',
                data_publicacao=timezone.now() - timedelta(minutes=idx),
            )
            for idx in range(8)
        ]

        response = self.client.get(reverse('noticias:public_list'))

        bottom_slots = response.context['bottom_slots']
        self.assertEqual(response.context['carousel_noticias'][0], noticias[0])
        self.assertEqual([slot['noticia'] for slot in bottom_slots], noticias[1:3])
        self.assertContains(response, reverse('noticias:archive'))
        self.assertContains(response, 'Ver todas as notícias publicadas')
        self.assertContains(response, 'noticias-home-list-card')

        self.assertContains(response, 'noticias-feature-bottom-left')

    def test_archive_lista_todas_as_noticias_publicadas(self):
        primeira = self.criar_noticia(titulo='Primeira noticia')
        segunda = self.criar_noticia(titulo='Segunda noticia')

        response = self.client.get(reverse('noticias:archive'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, primeira.titulo)
        self.assertContains(response, segunda.titulo)
        self.assertContains(response, reverse('noticias:public_list'))

    def test_archive_limita_vinte_noticias_por_pagina(self):
        for idx in range(21):
            self.criar_noticia(
                titulo=f'Noticia paginada {idx}',
                data_publicacao=timezone.now() - timedelta(minutes=idx),
            )

        response = self.client.get(reverse('noticias:archive'))
        page_2_response = self.client.get(f"{reverse('noticias:archive')}?page=2")

        self.assertEqual(len(response.context['noticias']), 20)
        self.assertTrue(response.context['is_paginated'])
        self.assertContains(response, 'Pagina 1 de 2')
        self.assertEqual(len(page_2_response.context['noticias']), 1)
        self.assertContains(page_2_response, 'Pagina 2 de 2')

    def test_detalhe_publico_bloqueia_noticia_nao_publicada(self):
        rascunho = self.criar_noticia(titulo='Rascunho', status=Noticia.Status.RASCUNHO, data_publicacao=None)

        response = self.client.get(reverse('noticias:public_detail', args=[rascunho.pk]))

        self.assertEqual(response.status_code, 404)

    def test_detalhe_publico_renderiza_pdf_anexo_apos_texto(self):
        noticia = self.criar_noticia(
            titulo='Com PDF',
            texto_noticia='A comunicação pública deve observar os princípios.',
            anexo_pdf='noticias/anexos/orientacoes.pdf',
        )

        response = self.client.get(reverse('noticias:public_detail', args=[noticia.pk]))

        self.assertContains(response, 'A comunicação pública deve observar os princípios.')
        self.assertContains(response, '<section class="noticia-pdf-anexo"')
        self.assertContains(response, reverse('noticias:pdf', args=[noticia.pk]))
        self.assertContains(response, 'orientacoes.pdf')

    def test_detalhe_publico_marca_urls_do_texto_como_links(self):
        noticia = self.criar_noticia(
            texto_noticia='Consulte http://intranet/ramais/ para buscar contatos.',
        )

        response = self.client.get(reverse('noticias:public_detail', args=[noticia.pk]))

        self.assertContains(response, '<a href="http://intranet/ramais/"')
        self.assertContains(response, '>http://intranet/ramais/</a>')

    def test_detalhe_publico_disponibiliza_anexo_nao_pdf_para_download(self):
        noticia = self.criar_noticia(
            titulo='Com anexo',
            texto_noticia='Texto com arquivo.',
            anexo_pdf='noticias/anexos/planilha.xlsx',
        )

        response = self.client.get(reverse('noticias:public_detail', args=[noticia.pk]))

        self.assertContains(response, 'Baixar anexo: planilha.xlsx')
        self.assertContains(response, 'href="/media/noticias/anexos/planilha.xlsx"')
        self.assertContains(response, 'download')
        self.assertNotContains(response, '<iframe class="noticia-pdf-viewer"')

    def test_pdf_anexo_e_servido_com_permissao_para_iframe(self):
        noticia = self.criar_noticia(titulo='Com PDF')
        noticia.anexo_pdf.save('orientacoes.pdf', pdf_teste(), save=True)

        response = self.client.get(reverse('noticias:pdf', args=[noticia.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
        self.assertEqual(response['Content-Disposition'], 'inline')

    def test_listagem_publica_nao_exige_login(self):
        response = self.client.get(reverse('noticias:public_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="/login/"')
        self.assertContains(response, 'Entrar')

    def test_raiz_e_home_redirecionam_para_noticias(self):
        root_response = self.client.get(reverse('root'))
        home_response = self.client.get(reverse('home'))

        self.assertRedirects(root_response, reverse('noticias:public_list'), fetch_redirect_response=False)
        self.assertRedirects(home_response, reverse('root'), fetch_redirect_response=False)

    def test_home_renderiza_atalhos_ativos_na_coluna_direita(self):
        self.criar_noticia(titulo='Destaque principal')
        Atalho.objects.create(
            titulo='Atalho ativo',
            imagem='atalhos/ativo.jpg',
            url='/licitacoes/',
            ordem=1,
            ativo=True,
        )
        Atalho.objects.create(
            titulo='Atalho inativo',
            imagem='atalhos/inativo.jpg',
            url='/navbar/',
            ordem=2,
            ativo=False,
        )

        response = self.client.get(reverse('noticias:public_list'))

        self.assertContains(response, 'noticias-home-layout')
        self.assertContains(response, 'noticias-home-main')
        self.assertContains(response, 'noticias-shortcuts-panel')
        self.assertContains(response, 'Atalho ativo')
        self.assertNotContains(response, 'Atalho inativo')
        self.assertContains(response, 'target="_blank"')

    def test_home_respeita_ordem_dos_atalhos(self):
        self.criar_noticia(titulo='Noticia base')
        Atalho.objects.create(
            titulo='Segundo',
            imagem='atalhos/segundo.jpg',
            url='/navbar/',
            ordem=2,
            ativo=True,
        )
        Atalho.objects.create(
            titulo='Primeiro',
            imagem='atalhos/primeiro.jpg',
            url='/licitacoes/',
            ordem=1,
            ativo=True,
        )

        response = self.client.get(reverse('noticias:public_list'))
        atalhos_ativos = list(response.context['atalhos_ativos'])

        self.assertEqual([atalho.titulo for atalho in atalhos_ativos], ['Primeiro', 'Segundo'])

    def test_home_superusuario_exibe_links_de_gerenciamento_de_noticias_e_atalhos(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')

        response = self.client.get(reverse('noticias:public_list'))

        self.assertContains(response, reverse('noticias:manage_list'))
        self.assertContains(response, reverse('atalhos:manage_list'))

    def test_home_mostra_estado_vazio_quando_nao_houver_atalhos(self):
        self.criar_noticia(titulo='Noticia base')

        response = self.client.get(reverse('noticias:public_list'))

        self.assertContains(response, 'Nenhum atalho ativo.')

    def test_gerenciamento_exige_superusuario(self):
        response = self.client.get(reverse('noticias:manage_list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_superusuario_cria_edita_e_exclui_noticia(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')

        create_response = self.client.post(
            reverse('noticias:create'),
            {
                'imagem_destaque': imagem_teste(),
                'anexo_pdf': pdf_teste(),
                'titulo': 'Nova noticia',
                'texto_noticia': 'Texto.',
                'status': Noticia.Status.RASCUNHO,
            },
        )
        noticia = Noticia.objects.get(titulo='Nova noticia')
        self.assertTrue(noticia.anexo_pdf.name.endswith('.pdf'))
        self.assertRedirects(create_response, reverse('noticias:manage_list'), fetch_redirect_response=False)

        update_response = self.client.post(
            reverse('noticias:update', args=[noticia.pk]),
            {
                'titulo': 'Noticia atualizada',
                'texto_noticia': 'Texto atualizado.',
                'status': Noticia.Status.RASCUNHO,
            },
        )
        noticia.refresh_from_db()
        self.assertEqual(noticia.titulo, 'Noticia atualizada')
        self.assertRedirects(update_response, reverse('noticias:manage_list'), fetch_redirect_response=False)

        delete_response = self.client.post(reverse('noticias:delete', args=[noticia.pk]))
        self.assertFalse(Noticia.objects.filter(pk=noticia.pk).exists())
        self.assertRedirects(delete_response, reverse('noticias:manage_list'), fetch_redirect_response=False)

    def test_superusuario_duplica_noticia_como_rascunho(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        original = self.criar_noticia(
            titulo='Original',
            texto_noticia='Texto original.',
            imagem_destaque='noticias/destaques/original.jpg',
            anexo_pdf='noticias/anexos/original.pdf',
            fixada=True,
        )

        response = self.client.post(reverse('noticias:duplicate', args=[original.pk]))

        duplicate = Noticia.objects.get(titulo='Copia de Original')
        self.assertEqual(duplicate.texto_noticia, original.texto_noticia)
        self.assertEqual(duplicate.imagem_destaque.name, original.imagem_destaque.name)
        self.assertEqual(duplicate.anexo_pdf.name, original.anexo_pdf.name)
        self.assertEqual(duplicate.status, Noticia.Status.RASCUNHO)
        self.assertIsNone(duplicate.data_publicacao)
        self.assertTrue(duplicate.fixada)
        self.assertRedirects(response, reverse('noticias:update', args=[duplicate.pk]), fetch_redirect_response=False)

    def test_gerenciamento_paginate_vinte_noticias_por_pagina(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        for idx in range(21):
            self.criar_noticia(
                titulo=f'Noticia gerenciada {idx}',
                data_publicacao=timezone.now() - timedelta(minutes=idx),
            )

        response = self.client.get(reverse('noticias:manage_list'))
        page_2_response = self.client.get(f"{reverse('noticias:manage_list')}?page=2")

        self.assertEqual(len(response.context['noticias']), 20)
        self.assertTrue(response.context['is_paginated'])
        self.assertContains(response, 'Pagina 1 de 2')
        self.assertContains(response, '&gt;')
        self.assertEqual(len(page_2_response.context['noticias']), 1)

    def test_gerenciamento_paginacao_compacta_acima_de_dez_paginas(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        for idx in range(221):
            self.criar_noticia(
                titulo=f'Noticia longa {idx}',
                status=Noticia.Status.RASCUNHO,
                data_publicacao=None,
            )

        response = self.client.get(f"{reverse('noticias:manage_list')}?status={Noticia.Status.RASCUNHO}&page=6")

        self.assertEqual(response.context['pagination_pages'], [1, 2, 6, 11, 12])
        self.assertContains(response, f'status={Noticia.Status.RASCUNHO}&amp;page=7')
        self.assertContains(response, f'status={Noticia.Status.RASCUNHO}&amp;page=11')
        self.assertNotContains(response, f'status={Noticia.Status.RASCUNHO}&amp;page=3')

    def test_comando_publica_somente_agendadas_vencidas(self):
        vencida = self.criar_noticia(
            titulo='Agendada vencida',
            status=Noticia.Status.AGENDADA,
            data_publicacao=timezone.now() - timedelta(minutes=1),
        )
        futura = self.criar_noticia(
            titulo='Agendada futura',
            status=Noticia.Status.AGENDADA,
            data_publicacao=timezone.now() + timedelta(days=1),
        )

        call_command('publicar_noticias_agendadas')

        vencida.refresh_from_db()
        futura.refresh_from_db()
        self.assertEqual(vencida.status, Noticia.Status.PUBLICADA)
        self.assertEqual(futura.status, Noticia.Status.AGENDADA)
