from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Dfd, DfdItemTabela, EtpTic, ItemTR, SessaoTR, TabelaItemLinha, TermoReferencia
from .services import (
    build_item_rows,
    duplicate_item,
    item_parent_for_tipo,
    move_item,
    red_marked_html,
    render_dfd_sections,
    render_etp_sections,
)


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


class DfdTests(TestCase):
    def test_render_numera_apenas_secoes_aplicaveis(self):
        dfd = Dfd.objects.create(
            nome='DFD',
            numero_processo='001/2026',
            informacoes_preliminares='Orgao: SEDS\n\nSetor: DIVTI',
            descricao_objeto='Primeiro paragrafo.\n\nSegundo paragrafo.',
            justificativa_necessidade='Justificativa.',
            responsaveis='Nenhum responsavel informado.',
        )

        secoes = render_dfd_sections(dfd)

        self.assertEqual(secoes[0]['entradas'], ['Orgao: SEDS', 'Setor: DIVTI'])
        self.assertEqual(secoes[1]['entradas'][0], '1.1. Primeiro paragrafo.')
        self.assertEqual(secoes[1]['entradas'][1], '1.2. Segundo paragrafo.')
        self.assertEqual(secoes[2]['entradas'][0], '2.1. Justificativa.')
        self.assertEqual(secoes[5]['entradas'], ['Nenhum responsavel informado.'])

    def test_criar_dfd_redireciona_para_edicao_secao_1(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')

        response = self.client.post(
            reverse('licitacoes:dfd_create'),
            {'nome': 'DFD', 'numero_processo': '001/2026'},
        )

        dfd = Dfd.objects.get(nome='DFD')
        self.assertRedirects(
            response,
            f"{reverse('licitacoes:dfd_edit', args=[dfd.pk])}?secao=1",
            fetch_redirect_response=False,
        )

    def test_editar_dfd_avanca_para_proxima_secao(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(nome='DFD', numero_processo='001/2026')

        response = self.client.post(
            f"{reverse('licitacoes:dfd_edit', args=[dfd.pk])}?secao=1",
            {'informacoes_preliminares': 'Orgao: SEDS', '_acao': 'proximo'},
        )

        dfd.refresh_from_db()
        self.assertEqual(dfd.secao_atual, 2)
        self.assertRedirects(
            response,
            f"{reverse('licitacoes:dfd_edit', args=[dfd.pk])}?secao=2",
            fetch_redirect_response=False,
        )

    def test_crud_linha_tabela_dfd(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(nome='DFD', numero_processo='001/2026')

        create_response = self.client.post(
            reverse('licitacoes:dfd_tabela_create', args=[dfd.pk]),
            {
                'item': '1',
                'equipamento': 'Notebook',
                'catmat': '123',
                'siafisico': '456',
                'quantidade': '2',
                'descricao': 'Equipamento portatil',
            },
        )
        linha = dfd.itens_tabela.get()
        self.assertEqual(linha.ordem, 1)
        self.assertRedirects(
            create_response,
            f"{reverse('licitacoes:dfd_edit', args=[dfd.pk])}?secao=2#dfd-tabela",
            fetch_redirect_response=False,
        )

        self.client.post(
            reverse('licitacoes:dfd_tabela_update', args=[dfd.pk, linha.pk]),
            {
                'item': '1',
                'equipamento': 'Desktop',
                'catmat': '123',
                'siafisico': '456',
                'quantidade': '3',
                'descricao': 'Equipamento fixo',
            },
        )
        linha.refresh_from_db()
        self.assertEqual(linha.equipamento, 'Desktop')
        self.assertEqual(linha.quantidade, 3)

        delete_response = self.client.post(reverse('licitacoes:dfd_tabela_delete', args=[dfd.pk, linha.pk]))
        self.assertFalse(DfdItemTabela.objects.filter(pk=linha.pk).exists())
        self.assertRedirects(
            delete_response,
            f"{reverse('licitacoes:dfd_edit', args=[dfd.pk])}?secao=2#dfd-tabela",
            fetch_redirect_response=False,
        )

    def test_exporta_dfd_docx_com_tabela(self):
        from io import BytesIO

        from docx import Document

        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(
            nome='DFD',
            numero_processo='001/2026',
            descricao_objeto='Objeto.',
            vinculacao_outro_dfd='Sem dependencia.',
        )
        DfdItemTabela.objects.create(dfd=dfd, ordem=1, item='1', equipamento='Notebook', quantidade=2)

        response = self.client.get(reverse('licitacoes:dfd_export', args=[dfd.pk]))

        document = Document(BytesIO(response.content))
        paragraphs = '\n'.join(p.text for p in document.paragraphs)
        table_text = '\n'.join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
        self.assertIn('DFD - DFD', paragraphs)
        self.assertIn('1.1. Objeto.', paragraphs)
        self.assertIn('4.1. Sem dependencia.', paragraphs)
        self.assertIn('Notebook', table_text)


class RedMarkTests(TestCase):
    def test_renderiza_marcacao_vermelha_com_asteriscos_pareados_e_palavra_solteira(self):
        html = red_marked_html('Texto *vermelho* e *alerta')

        self.assertIn('<span class="text-danger">vermelho</span>', html)
        self.assertIn('<span class="text-danger">alerta</span>', html)
        self.assertNotIn('*vermelho*', html)


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
        self.assertTrue(found[item.id]['pode_tabela_itens'])
        self.assertFalse(found[sub.id]['pode_tabela_itens'])

    def test_numera_inciso_criado_a_partir_de_inciso_como_irmao(self):
        item = ItemTR.objects.create(sessao=self.sessao, texto='Item', ordem=1)
        sub = ItemTR.objects.create(sessao=self.sessao, parent=item, texto='Subitem', ordem=1)
        primeiro = ItemTR.objects.create(sessao=self.sessao, parent=sub, tipo=ItemTR.Tipo.INCISO, texto='Primeiro', ordem=1)
        parent = item_parent_for_tipo(primeiro, ItemTR.Tipo.INCISO)
        segundo = ItemTR.objects.create(sessao=self.sessao, parent=parent, tipo=ItemTR.Tipo.INCISO, texto='Segundo', ordem=2)
        rows = build_item_rows(self.sessao)
        found = {row['item'].id: row for row in rows}
        self.assertEqual(segundo.parent_id, sub.id)
        self.assertEqual(found[primeiro.id]['enum_prefix'], 'I)')
        self.assertEqual(found[segundo.id]['enum_prefix'], 'II)')

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

    def test_mover_como_primeiro_subitem_empurra_filhos_existentes(self):
        destino = ItemTR.objects.create(sessao=self.sessao, texto='Destino', ordem=1)
        primeiro = ItemTR.objects.create(sessao=self.sessao, parent=destino, texto='Primeiro filho', ordem=1)
        segundo = ItemTR.objects.create(sessao=self.sessao, parent=destino, texto='Segundo filho', ordem=2)
        item = ItemTR.objects.create(sessao=self.sessao, texto='Item movido', ordem=2)

        move_item(item, destino, 'child', child_position=1)

        item.refresh_from_db()
        primeiro.refresh_from_db()
        segundo.refresh_from_db()
        self.assertEqual(item.parent_id, destino.id)
        self.assertEqual(item.ordem, 1)
        self.assertEqual(primeiro.ordem, 2)
        self.assertEqual(segundo.ordem, 3)

    def test_duplicar_item_copia_subitens(self):
        a = ItemTR.objects.create(sessao=self.sessao, texto='A', ordem=1)
        b = ItemTR.objects.create(sessao=self.sessao, texto='B', ordem=2)
        child = ItemTR.objects.create(sessao=self.sessao, parent=a, texto='Filho', ordem=1)
        ItemTR.objects.create(sessao=self.sessao, parent=child, texto='Neto', ordem=1)
        TabelaItemLinha.objects.create(item=a, ordem=1, descricao='Notebook', quantidade='2.00')

        duplicate = duplicate_item(a, b, 'after')
        duplicate.refresh_from_db()

        self.assertEqual(duplicate.texto, 'A')
        self.assertEqual(duplicate.parent_id, None)
        self.assertEqual(duplicate.ordem, 3)
        duplicate_child = duplicate.filhos.get()
        self.assertEqual(duplicate_child.texto, 'Filho')
        self.assertEqual(duplicate_child.filhos.get().texto, 'Neto')
        self.assertEqual(duplicate.tabela_linhas.get().descricao, 'Notebook')

    def test_tabela_item_create_disponivel_somente_no_item_1_1(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        item_1_1 = ItemTR.objects.create(sessao=self.sessao, texto='Item 1.1', ordem=1)
        item_1_2 = ItemTR.objects.create(sessao=self.sessao, texto='Item 1.2', ordem=2)

        response = self.client.post(
            reverse('licitacoes:tabela_item_create', args=[self.sessao.pk, item_1_1.pk]),
            {
                'descricao': 'Notebook',
                'catmat_catser': '123',
                'siafisico': '456',
                'unidade_fornecimento': 'Unidade',
                'quantidade': '2.00',
            },
        )

        linha = item_1_1.tabela_linhas.get()
        self.assertEqual(linha.ordem, 1)
        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#tabela-itens-{item_1_1.pk}",
            fetch_redirect_response=False,
        )

        bloqueado = self.client.get(reverse('licitacoes:tabela_item_create', args=[self.sessao.pk, item_1_2.pk]))
        self.assertEqual(bloqueado.status_code, 404)

    def test_detail_renderiza_tabela_no_item_1_1(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        item = ItemTR.objects.create(sessao=self.sessao, texto='Item 1.1', ordem=1)
        TabelaItemLinha.objects.create(item=item, ordem=1, descricao='Notebook', quantidade='2.00')

        response = self.client.get(reverse('licitacoes:tr_detail', args=[self.termo.pk]))

        self.assertContains(response, 'Itens da tabela do item 1.1')
        self.assertContains(response, 'Notebook')

    def test_detail_renderiza_marcacao_vermelha_no_item(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        ItemTR.objects.create(sessao=self.sessao, texto='Texto *vermelho*', ordem=1)

        response = self.client.get(reverse('licitacoes:tr_detail', args=[self.termo.pk]))

        self.assertContains(response, '<span class="text-danger">vermelho</span>')

    def test_exporta_marcacao_vermelha_no_docx(self):
        from io import BytesIO

        from docx import Document

        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        ItemTR.objects.create(sessao=self.sessao, texto='Texto *vermelho*', ordem=1)

        response = self.client.get(reverse('licitacoes:tr_export', args=[self.termo.pk]))
        document = Document(BytesIO(response.content))
        runs = [run for paragraph in document.paragraphs for run in paragraph.runs]
        red_run = next(run for run in runs if run.text == 'vermelho')

        self.assertEqual(str(red_run.font.color.rgb), 'FF0000')

    def test_duplicar_item_pela_view_volta_para_item_duplicado(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        item = ItemTR.objects.create(sessao=self.sessao, texto='Item original', ordem=1)

        response = self.client.post(
            reverse('licitacoes:item_duplicate', args=[self.sessao.pk, item.pk]),
            {'target': f'sessao:{self.sessao.pk}', 'action': 'child'},
        )

        duplicate = ItemTR.objects.exclude(pk=item.pk).get(texto='Item original')
        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#item-{duplicate.pk}",
            fetch_redirect_response=False,
        )

    def test_editar_item_volta_para_item_editado(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        item = ItemTR.objects.create(sessao=self.sessao, texto='Texto antigo', ordem=1)

        response = self.client.post(
            reverse('licitacoes:item_update', args=[self.sessao.pk, item.pk]),
            {'texto': 'Texto atualizado'},
        )

        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#item-{item.pk}",
            fetch_redirect_response=False,
        )

    def test_criar_item_volta_para_item_criado(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')

        response = self.client.post(
            reverse('licitacoes:item_create', args=[self.sessao.pk]),
            {'texto': 'Item novo'},
        )

        item = ItemTR.objects.get(texto='Item novo')
        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#item-{item.pk}",
            fetch_redirect_response=False,
        )

    def test_criar_subitem_volta_para_subitem_criado(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        parent = ItemTR.objects.create(sessao=self.sessao, texto='Item pai', ordem=1)

        response = self.client.post(
            reverse('licitacoes:item_child_create', args=[self.sessao.pk, parent.pk]),
            {'texto': 'Subitem novo'},
        )

        item = ItemTR.objects.get(texto='Subitem novo')
        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#item-{item.pk}",
            fetch_redirect_response=False,
        )

    def test_excluir_item_volta_para_proximo_item(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        item = ItemTR.objects.create(sessao=self.sessao, texto='A', ordem=1)
        next_item = ItemTR.objects.create(sessao=self.sessao, texto='B', ordem=2)

        response = self.client.post(reverse('licitacoes:item_delete', args=[self.sessao.pk, item.pk]))

        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#item-{next_item.pk}",
            fetch_redirect_response=False,
        )

    def test_excluir_ultimo_item_volta_para_item_anterior(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        previous_item = ItemTR.objects.create(sessao=self.sessao, texto='A', ordem=1)
        item = ItemTR.objects.create(sessao=self.sessao, texto='B', ordem=2)

        response = self.client.post(reverse('licitacoes:item_delete', args=[self.sessao.pk, item.pk]))

        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#item-{previous_item.pk}",
            fetch_redirect_response=False,
        )

    def test_excluir_unico_item_raiz_volta_para_sessao(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        item = ItemTR.objects.create(sessao=self.sessao, texto='A', ordem=1)

        response = self.client.post(reverse('licitacoes:item_delete', args=[self.sessao.pk, item.pk]))

        self.assertRedirects(
            response,
            f"{reverse('licitacoes:tr_detail', args=[self.termo.pk])}#sessao-{self.sessao.pk}",
            fetch_redirect_response=False,
        )
