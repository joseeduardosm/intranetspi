# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Validar o fluxo de geração, prévia e download da assinatura de e-mail.

import io

from PIL import Image
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.urls import reverse

from .services import PNG_HEIGHT, PNG_WIDTH, SECRETARIA_FIXA, render_signature_png


class AssinaturaEmailTests(TestCase):
    """Cobre autenticação, preenchimento inicial, renderização e download do PNG."""

    def setUp(self):
        # Usuário de referência com perfil preenchido para simular o fluxo mais comum.
        self.user = get_user_model().objects.create_user(
            username='jose',
            password='123',
            email='jose@sp.gov.br',
        )
        perfil = self.user.perfil
        perfil.nome_completo = 'Jose da Silva'
        perfil.cargo = 'Analista'
        perfil.setor = 'Departamento de Tecnologia'
        perfil.ramal = '8234'
        perfil.save()

    def test_usuario_anonimo_e_redirecionado_para_login(self):
        response = self.client.get(reverse('assinatura_e_mail:form'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_formulario_pre_preenche_dados_do_usuario(self):
        self.client.login(username='jose', password='123')
        response = self.client.get(reverse('assinatura_e_mail:form'))
        form = response.context['form']
        self.assertEqual(form.initial['nome_completo'], 'Jose da Silva')
        self.assertEqual(form.initial['cargo_funcao'], 'Analista')
        self.assertEqual(form.initial['departamento'], 'Departamento de Tecnologia')
        self.assertEqual(form.initial['email'], 'jose@sp.gov.br')
        self.assertEqual(form.initial['ramal'], '8234')

    def test_formulario_funciona_com_perfil_sem_dados(self):
        outro = get_user_model().objects.create_user(username='ana', password='123', email='ana@sp.gov.br')
        outro.perfil.nome_completo = ''
        outro.perfil.cargo = ''
        outro.perfil.setor = ''
        outro.perfil.ramal = ''
        outro.perfil.save()
        self.client.login(username='ana', password='123')
        response = self.client.get(reverse('assinatura_e_mail:form'))
        form = response.context['form']
        self.assertEqual(form.initial['email'], 'ana@sp.gov.br')
        self.assertEqual(form.initial['nome_completo'], '')

    def test_post_valido_gera_previa_e_link_de_download(self):
        self.client.login(username='jose', password='123')
        response = self.client.post(
            reverse('assinatura_e_mail:form'),
            {
                'nome_completo': 'Jose da Silva',
                'cargo_funcao': 'Analista de Sistemas',
                'departamento': 'Departamento de Tecnologia',
                'email': 'jose@sp.gov.br',
                'ramal': '8234',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data:image/png;base64,')
        self.assertContains(response, reverse('assinatura_e_mail:download'))

    def test_download_retorna_png_no_tamanho_correto(self):
        self.client.login(username='jose', password='123')
        token = signing.dumps(
            {
                'nome_completo': 'Jose da Silva',
                'cargo_funcao': 'Analista de Sistemas',
                'departamento': 'Departamento de Tecnologia',
                'email': 'jose@sp.gov.br',
                'ramal': '8234',
            }
        )
        response = self.client.get(reverse('assinatura_e_mail:download'), {'token': token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        image = Image.open(io.BytesIO(response.content))
        self.assertEqual(image.size, (PNG_WIDTH, PNG_HEIGHT))

    def test_renderizacao_nao_quebra_com_campos_longos(self):
        png_bytes = render_signature_png(
            {
                'nome_completo': 'NOME COMPLETO EXTREMAMENTE LONGO PARA TESTE DE REDUCAO DE FONTE',
                'cargo_funcao': 'Cargo/Função bastante descritivo para validar o ajuste fino do layout final',
                'departamento': 'Departamento com nome comprido para exercitar a quebra controlada',
                'email': 'nome.sobrenome.extenso@sp.gov.br',
                'ramal': '9999',
            }
        )
        image = Image.open(io.BytesIO(png_bytes))
        self.assertEqual(image.size, (PNG_WIDTH, PNG_HEIGHT))

    def test_secretaria_fixa_esta_disponivel_no_servico(self):
        self.assertEqual(SECRETARIA_FIXA, 'Secretaria de Parcerias em Investimentos')
