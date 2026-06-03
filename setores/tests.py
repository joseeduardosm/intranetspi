from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from usuarios.models import UsuarioPerfil

from .forms import SetorForm
from .models import SetorNode, UserSetorMembership
from .services import build_setor_tree, ensure_user_primary_setor


User = get_user_model()


class SetoresTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(username='admin_setor', password='123', email='admin@example.com')
        self.user = User.objects.create_user(username='joao_setor', password='123', email='joao@example.com')
        self.other = User.objects.create_user(username='maria_setor', password='123', email='maria@example.com')

    def create_setor(self, name='Financeiro', **kwargs):
        return SetorNode.objects.create(group=Group.objects.create(name=name), **kwargs)

    def test_criacao_de_setor_sem_pai(self):
        setor = self.create_setor()
        self.assertEqual(setor.group.name, 'Financeiro')
        self.assertIsNone(setor.parent)

    def test_criacao_de_setor_com_pai(self):
        pai = self.create_setor(name='Diretoria')
        filho = self.create_setor(name='Compras', parent=pai)
        self.assertEqual(filho.parent, pai)

    def test_criacao_de_setor_com_lider(self):
        setor = self.create_setor(name='Jurídico', lider=self.user)
        self.assertEqual(setor.lider, self.user)

    def test_vinculo_de_multiplos_usuarios_ao_setor(self):
        setor = self.create_setor()
        form = SetorForm(
            data={
                'nome': setor.group.name,
                'parent': '',
                'lider': '',
                'ativo': 'on',
                'usuarios': [self.user.pk, self.other.pk],
            },
            instance=setor,
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(setor.memberships.count(), 2)

    def test_bloqueia_auto_referencia_e_ciclo(self):
        pai = self.create_setor(name='Pai')
        filho = self.create_setor(name='Filho', parent=pai)
        pai.parent = filho
        with self.assertRaisesMessage(Exception, 'Ciclo detectado'):
            pai.full_clean()

    def test_listagem_exibe_colunas_principais(self):
        self.create_setor()
        self.client.login(username='joao_setor', password='123')
        response = self.client.get(reverse('setores:list'))
        self.assertContains(response, 'ID')
        self.assertContains(response, 'Nome do grupo')
        self.assertContains(response, 'Grupo pai')
        self.assertContains(response, '...')

    def test_usuario_comum_ve_listagem_e_organograma_mas_nao_cria(self):
        self.create_setor()
        self.client.login(username='joao_setor', password='123')
        self.assertEqual(self.client.get(reverse('setores:list')).status_code, 200)
        self.assertEqual(self.client.get(reverse('setores:organograma')).status_code, 200)
        self.assertEqual(self.client.get(reverse('setores:create')).status_code, 403)

    def test_superusuario_faz_crud_completo(self):
        self.client.login(username='admin_setor', password='123')
        response = self.client.post(
            reverse('setores:create'),
            {'nome': 'Planejamento', 'parent': '', 'lider': self.user.pk, 'ativo': 'on', 'usuarios': [self.user.pk]},
        )
        self.assertRedirects(response, reverse('setores:list'), fetch_redirect_response=False)
        setor = SetorNode.objects.get(group__name='Planejamento')
        self.assertEqual(setor.lider, self.user)

    def test_formulario_usuario_sincroniza_membership_e_texto_legado(self):
        setor = self.create_setor()
        ensure_user_primary_setor(self.user, setor)
        perfil = self.user.perfil
        perfil.refresh_from_db()
        self.assertEqual(perfil.setor, setor.group.name)
        self.assertTrue(UserSetorMembership.objects.filter(user=self.user, setor=setor).exists())

    def test_reset_de_setor_manual_e_recadastro(self):
        perfil = self.user.perfil
        perfil.setor = 'Texto manual'
        perfil.ultimo_recadastro_em = perfil.atualizado_em
        perfil.save()
        perfil.setor = ''
        perfil.ultimo_recadastro_em = None
        perfil.save()
        perfil.refresh_from_db()
        self.assertEqual(perfil.setor, '')
        self.assertIsNone(perfil.ultimo_recadastro_em)

    def test_organogramas_renderizam_setor_lider_e_usuarios(self):
        setor = self.create_setor(name='Tecnologia', lider=self.user)
        UserSetorMembership.objects.create(user=self.user, setor=setor)
        self.client.login(username='joao_setor', password='123')
        response = self.client.get(reverse('setores:organograma'))
        self.assertContains(response, 'Secretaria de Parcerias em Investimentos')
        self.assertContains(response, 'Tecnologia')
        self.assertContains(response, self.user.username)
        self.assertContains(response, 'ramalContactModal')

    def test_exclusao_bloqueada_para_setor_com_filhos_ou_membros(self):
        self.client.login(username='admin_setor', password='123')
        pai = self.create_setor(name='Pai')
        self.create_setor(name='Filho', parent=pai)
        response = self.client.post(reverse('setores:delete', args=[pai.pk]))
        self.assertRedirects(response, reverse('setores:list'), fetch_redirect_response=False)
        self.assertTrue(SetorNode.objects.filter(pk=pai.pk).exists())
