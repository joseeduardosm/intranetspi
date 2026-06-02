import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import AtalhoForm
from .models import Atalho


def imagem_teste():
    return SimpleUploadedFile(
        'atalho.png',
        b'GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02L\x01\x00;',
        content_type='image/png',
    )


class AtalhosTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def test_form_aceita_url_interna(self):
        form = AtalhoForm(
            data={
                'titulo': 'Licitacoes',
                'url': '/licitacoes/',
                'ordem': 1,
                'ativo': 'on',
            },
            files={'imagem': imagem_teste()},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_aceita_url_externa(self):
        form = AtalhoForm(
            data={
                'titulo': 'Portal',
                'url': 'https://www.saopaulo.sp.gov.br/',
                'ordem': 2,
                'ativo': 'on',
            },
            files={'imagem': imagem_teste()},
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejeita_url_invalida(self):
        form = AtalhoForm(
            data={
                'titulo': 'Invalido',
                'url': 'ftp://servidor/invalido',
                'ordem': 3,
                'ativo': 'on',
            },
            files={'imagem': imagem_teste()},
        )

        self.assertFalse(form.is_valid())
        self.assertIn('url', form.errors)

    def test_crud_exige_superusuario(self):
        response = self.client.get(reverse('atalhos:manage_list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_superusuario_acessa_listagem(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        Atalho.objects.create(
            titulo='Licitacoes',
            imagem='atalhos/lic.jpg',
            url='/licitacoes/',
            ordem=1,
            ativo=True,
        )

        self.client.login(username='admin', password='123')
        response = self.client.get(reverse('atalhos:manage_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Gerenciar Atalhos')
        self.assertContains(response, 'Licitacoes')
