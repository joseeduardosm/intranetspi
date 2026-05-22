from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import NavbarItem
from .services import active_navbar_tree


class NavbarTests(TestCase):
    def test_active_navbar_tree_ordena_pais_e_filhos_ativos(self):
        parent = NavbarItem.objects.create(titulo='SEF', url='/sef/', ordem=2)
        child_b = NavbarItem.objects.create(titulo='Fornecedores', url='/fornecedores/', parent=parent, ordem=2)
        child_a = NavbarItem.objects.create(titulo='Gestores', url='/gestores/', parent=parent, ordem=1)
        NavbarItem.objects.create(titulo='Inativo', url='/inativo/', parent=parent, ordem=3, ativo=False)
        first = NavbarItem.objects.create(titulo='Helpdesk', url='/helpdesk/', ordem=1)

        tree = active_navbar_tree()

        self.assertEqual([entry['item'] for entry in tree], [first, parent])
        self.assertEqual(tree[1]['children'], [child_a, child_b])

    def test_model_bloqueia_mais_de_um_nivel_de_submenu(self):
        parent = NavbarItem.objects.create(titulo='Pai', url='/pai/')
        child = NavbarItem.objects.create(titulo='Filho', url='/filho/', parent=parent)
        grandchild = NavbarItem(titulo='Neto', url='/neto/', parent=child)

        with self.assertRaises(ValidationError):
            grandchild.full_clean()

    def test_navbar_renderiza_item_dropdown_e_link_externo(self):
        parent = NavbarItem.objects.create(titulo='SEF', ordem=1)
        NavbarItem.objects.create(titulo='Gestores', url='/gestores/', parent=parent, ordem=1)
        NavbarItem.objects.create(titulo='Portal SP', url='https://www.saopaulo.sp.gov.br/', ordem=2)
        NavbarItem.objects.create(titulo='Inativo', url='/inativo/', ordem=3, ativo=False)

        response = self.client.get(reverse('noticias:public_list'))

        self.assertContains(response, 'SEF')
        self.assertContains(response, 'Gestores')
        self.assertContains(response, 'dropdown-toggle')
        self.assertContains(response, 'href="#" role="button" data-bs-toggle="dropdown"')
        self.assertContains(response, 'https://www.saopaulo.sp.gov.br/')
        self.assertContains(response, 'target="_blank" rel="noopener"')
        self.assertNotContains(response, 'Inativo')

    def test_form_aceita_url_em_branco_para_menu_dropdown(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')

        response = self.client.post(
            reverse('navbar:create'),
            {
                'titulo': 'SEF',
                'url': '',
                'ordem': 1,
                'ativo': 'on',
            },
        )

        self.assertRedirects(response, reverse('navbar:manage_list'), fetch_redirect_response=False)
        self.assertEqual(NavbarItem.objects.get(titulo='SEF').url, '')

    def test_gerenciamento_exige_superusuario(self):
        response = self.client.get(reverse('navbar:manage_list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_superusuario_cria_edita_e_exclui_item(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')

        create_response = self.client.post(
            reverse('navbar:create'),
            {
                'titulo': 'Noticias',
                'url': '/noticias/',
                'ordem': 1,
                'ativo': 'on',
            },
        )
        item = NavbarItem.objects.get(titulo='Noticias')
        self.assertRedirects(create_response, reverse('navbar:manage_list'), fetch_redirect_response=False)

        update_response = self.client.post(
            reverse('navbar:update', args=[item.pk]),
            {
                'titulo': 'Noticias atualizadas',
                'url': '/noticias/todas/',
                'ordem': 2,
                'ativo': 'on',
                'abrir_nova_aba': 'on',
            },
        )
        item.refresh_from_db()
        self.assertEqual(item.titulo, 'Noticias atualizadas')
        self.assertEqual(item.url, '/noticias/todas/')
        self.assertTrue(item.abrir_nova_aba)
        self.assertRedirects(update_response, reverse('navbar:manage_list'), fetch_redirect_response=False)

        delete_response = self.client.post(reverse('navbar:delete', args=[item.pk]))
        self.assertFalse(NavbarItem.objects.filter(pk=item.pk).exists())
        self.assertRedirects(delete_response, reverse('navbar:manage_list'), fetch_redirect_response=False)
