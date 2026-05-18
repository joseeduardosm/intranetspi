from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import EtpTic, ItemTR, SessaoTR, TermoReferencia
from .services import build_item_rows, move_item, render_etp_sections


class LoginTests(TestCase):
    def test_login_rejeita_usuario_nao_superuser(self):
        User = get_user_model()
        User.objects.create_user(username='comum', password='123')
        response = self.client.post(reverse('login'), {'username': 'comum', 'password': '123'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class EtpTicTests(TestCase):
    def test_render_numera_paragrafos_por_secao(self):
        etp = EtpTic.objects.create(
            nome='Contratacao',
            numero_processo='001/2026',
            descricao_necessidade='Primeiro paragrafo.\n\nSegundo paragrafo.',
        )
        secao = render_etp_sections(etp)[1]
        self.assertEqual(secao['entradas'][0], '2.1. Primeiro paragrafo.')
        self.assertEqual(secao['entradas'][1], '2.2. Segundo paragrafo.')


class TrTests(TestCase):
    def setUp(self):
        self.termo = TermoReferencia.objects.create(nome='TR', numero_processo='002/2026')
        self.sessao = SessaoTR.objects.create(termo=self.termo, titulo='Objeto', ordem=1)

    def test_numera_item_subitem_inciso_e_alinea(self):
        item = ItemTR.objects.create(sessao=self.sessao, texto='Item', ordem=1)
        sub = ItemTR.objects.create(sessao=self.sessao, parent=item, texto='Subitem', ordem=1)
        inciso = ItemTR.objects.create(sessao=self.sessao, parent=sub, tipo=ItemTR.Tipo.INCISO, texto='Inciso', ordem=1)
        alinea = ItemTR.objects.create(sessao=self.sessao, parent=sub, tipo=ItemTR.Tipo.ALINEA, texto='Alinea', ordem=2)
        rows = build_item_rows(self.sessao)
        found = {row['item'].id: row for row in rows}
        self.assertEqual(found[item.id]['indice'], '1.1')
        self.assertEqual(found[sub.id]['indice'], '1.1.1')
        self.assertEqual(found[inciso.id]['enum_prefix'], 'I)')
        self.assertEqual(found[alinea.id]['enum_prefix'], 'a)')

    def test_mover_bloqueia_descendente_e_renumera(self):
        a = ItemTR.objects.create(sessao=self.sessao, texto='A', ordem=1)
        b = ItemTR.objects.create(sessao=self.sessao, texto='B', ordem=2)
        child = ItemTR.objects.create(sessao=self.sessao, parent=a, texto='Filho', ordem=1)
        with self.assertRaises(ValueError):
            move_item(a, child, 'child')
        move_item(b, a, 'child')
        b.refresh_from_db()
        self.assertEqual(b.parent_id, a.id)
        self.assertEqual(b.ordem, 2)
