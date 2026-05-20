from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Dfd, DfdItemTabela, EtpTic, ItemTR, SessaoTR, TabelaItemLinha, TermoReferencia
from .services import (
    build_item_rows,
    duplicate_item,
    duplicate_termo,
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
        self.assertEqual(secoes[1]['entradas'][0], '1.1. Primeiro paragrafo.\n\nSegundo paragrafo.')
        self.assertEqual(secoes[1]['entradas_apos_tabela'], [Dfd.OBJETO_NAO_LUXO_PADRAO])
        self.assertEqual(secoes[2]['entradas'][0], '2.1. Justificativa.')
        self.assertEqual(secoes[5]['entradas'], ['Nenhum responsavel informado.'])

    def test_render_dfd_item_1_2_normaliza_prefixo_na_exportacao(self):
        dfd = Dfd.objects.create(
            nome='DFD',
            numero_processo='001/2026',
            descricao_objeto='Objeto.',
            objeto_nao_luxo='Item 1.2: O objeto desta contratação não se enquadra como sendo de bem de luxo.',
        )

        secao_objeto = render_dfd_sections(dfd)[1]

        self.assertEqual(
            secao_objeto['entradas_apos_tabela'],
            ['1.2. O objeto desta contratação não se enquadra como sendo de bem de luxo.'],
        )

    def test_preview_dfd_renderiza_responsaveis_centralizado(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(
            nome='DFD',
            numero_processo='001/2026',
            responsaveis='Responsavel centralizado.',
        )

        response = self.client.get(reverse('licitacoes:dfd_preview', args=[dfd.pk]))

        self.assertContains(response, '<h2 class="h5 text-center">Responsaveis</h2>')
        self.assertContains(response, '<p class="mb-0 text-center">Responsavel centralizado.</p>')

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

    def test_concluir_dfd_salva_responsaveis_da_secao_atual(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(nome='DFD', numero_processo='001/2026', secao_atual=6)

        response = self.client.post(
            f"{reverse('licitacoes:dfd_edit', args=[dfd.pk])}?secao=6",
            {'responsaveis': 'Responsavel salvo.', '_acao': 'concluir'},
        )

        dfd.refresh_from_db()
        self.assertEqual(dfd.responsaveis, 'Responsavel salvo.')
        self.assertEqual(dfd.status, Dfd.Status.CONCLUIDO)
        self.assertRedirects(
            response,
            reverse('licitacoes:dfd_preview', args=[dfd.pk]),
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
                'especificacao': 'Notebook',
                'catmat': '123',
                'siafisico': '456',
                'unidade_medida': 'Unidade',
                'quantidade': '2',
                'valor_unitario': '100.50',
                'valor_total': '201.00',
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
                'especificacao': 'Desktop',
                'catmat': '123',
                'siafisico': '456',
                'unidade_medida': 'Unidade',
                'quantidade': '3',
                'valor_unitario': '150.00',
                'valor_total': '450.00',
            },
        )
        linha.refresh_from_db()
        self.assertEqual(linha.especificacao, 'Desktop')
        self.assertEqual(linha.quantidade, 3)
        self.assertEqual(str(linha.valor_total), '450.00')

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
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(
            nome='DFD',
            numero_processo='001/2026',
            informacoes_preliminares='Orgao: SEDS',
            descricao_objeto='Objeto.',
            vinculacao_outro_dfd='Sem dependencia.',
            responsaveis='Responsavel centralizado.',
        )
        DfdItemTabela.objects.create(
            dfd=dfd,
            ordem=1,
            especificacao='Notebook',
            siafisico='456',
            quantidade='2.00',
            valor_unitario='100.50',
            valor_total='201.00',
        )

        response = self.client.get(reverse('licitacoes:dfd_export', args=[dfd.pk]))

        document = Document(BytesIO(response.content))
        paragraphs = '\n'.join(p.text for p in document.paragraphs)
        table_text = '\n'.join(cell.text for table in document.tables for row in table.rows for cell in row.cells)
        self.assertIn('DFD - DFD', paragraphs)
        self.assertIn('1.1. Objeto.', paragraphs)
        self.assertIn(Dfd.OBJETO_NAO_LUXO_PADRAO, paragraphs)
        self.assertIn('4.1. Sem dependencia.', paragraphs)
        self.assertIn('Notebook', table_text)
        self.assertIn('SIAFISICO', table_text)
        self.assertIn('456', table_text)
        self.assertIn('Valor total', table_text)
        info_paragraph = next(p for p in document.paragraphs if p.text == 'Orgao: SEDS')
        object_paragraph = next(p for p in document.paragraphs if p.text == '1.1. Objeto.')
        responsaveis_paragraph = next(p for p in document.paragraphs if p.text == 'Responsavel centralizado.')
        self.assertEqual(info_paragraph.alignment, WD_ALIGN_PARAGRAPH.LEFT)
        self.assertEqual(object_paragraph.alignment, WD_ALIGN_PARAGRAPH.JUSTIFY)
        self.assertEqual(responsaveis_paragraph.alignment, WD_ALIGN_PARAGRAPH.CENTER)
        self.assertTrue(all(run.font.name == 'Verdana' for run in object_paragraph.runs if run.text))
        self.assertTrue(all(run.font.size.pt == 10 for run in object_paragraph.runs if run.text))
        header_run = document.tables[0].rows[0].cells[0].paragraphs[0].runs[0]
        body_run = document.tables[0].rows[1].cells[1].paragraphs[0].runs[0]
        self.assertEqual(header_run.font.name, 'Verdana')
        self.assertEqual(header_run.font.size.pt, 8)
        self.assertEqual(body_run.font.name, 'Verdana')
        self.assertEqual(body_run.font.size.pt, 8)

    def test_preview_dfd_renderiza_marcacao_vermelha(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(
            nome='DFD',
            numero_processo='001/2026',
            descricao_objeto='Texto *vermelho*',
            objeto_nao_luxo='1.2. Item *destacado*',
        )
        DfdItemTabela.objects.create(
            dfd=dfd,
            ordem=1,
            especificacao='Notebook *especial*',
            quantidade='2.00',
            valor_unitario='100.50',
            valor_total='201.00',
        )

        response = self.client.get(reverse('licitacoes:dfd_preview', args=[dfd.pk]))

        self.assertContains(response, '<span class="text-danger">vermelho</span>')
        self.assertContains(response, '<span class="text-danger">destacado</span>')
        self.assertContains(response, '<span class="text-danger">especial</span>')

    def test_exporta_dfd_marcacao_vermelha_no_docx(self):
        from io import BytesIO

        from docx import Document

        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        dfd = Dfd.objects.create(
            nome='DFD',
            numero_processo='001/2026',
            descricao_objeto='Texto *vermelho*',
            objeto_nao_luxo='1.2. Item *destacado*',
        )
        DfdItemTabela.objects.create(
            dfd=dfd,
            ordem=1,
            especificacao='Notebook *especial*',
            quantidade='2.00',
            valor_unitario='100.50',
            valor_total='201.00',
        )

        response = self.client.get(reverse('licitacoes:dfd_export', args=[dfd.pk]))
        document = Document(BytesIO(response.content))
        runs = [run for paragraph in document.paragraphs for run in paragraph.runs]
        runs += [run for table in document.tables for row in table.rows for cell in row.cells for paragraph in cell.paragraphs for run in paragraph.runs]
        red_texts = {run.text for run in runs if run.font.color.rgb and str(run.font.color.rgb) == 'FF0000'}

        self.assertIn('vermelho', red_texts)
        self.assertIn('destacado', red_texts)
        self.assertIn('especial', red_texts)


class RedMarkTests(TestCase):
    def test_renderiza_marcacao_vermelha_com_asteriscos_pareados_e_palavra_solteira(self):
        html = red_marked_html('Texto *vermelho* e *alerta')

        self.assertIn('<span class="text-danger">vermelho</span>', html)
        self.assertIn('<span class="text-danger">alerta</span>', html)
        self.assertNotIn('*vermelho*', html)

    def test_renderiza_marcacao_vermelha_em_palavra_solteira_e_bloco_com_espaco(self):
        html = red_marked_html('Texto *destaque\n\n* paragrafo inteiro*')

        self.assertIn('<span class="text-danger">destaque</span>', html)
        self.assertIn('<span class="text-danger"> paragrafo inteiro</span>', html)

    def test_renderiza_marcacao_vermelha_em_frase_pareada_com_um_ou_dois_asteriscos(self):
        html = red_marked_html('Texto *frase inteira marcada* e **outra frase marcada**')

        self.assertIn('<span class="text-danger">frase inteira marcada</span>', html)
        self.assertIn('<span class="text-danger">outra frase marcada</span>', html)


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

    def test_duplicar_tr_copia_sessoes_itens_e_tabelas(self):
        sessao_2 = SessaoTR.objects.create(termo=self.termo, titulo='Outra sessao', ordem=2)
        item = ItemTR.objects.create(sessao=self.sessao, texto='Item original', ordem=1)
        child = ItemTR.objects.create(sessao=self.sessao, parent=item, texto='Subitem original', ordem=1)
        TabelaItemLinha.objects.create(item=item, ordem=1, descricao='Notebook', quantidade='2.00')
        ItemTR.objects.create(sessao=sessao_2, texto='Item sessao 2', ordem=1)

        duplicate = duplicate_termo(self.termo)

        self.assertEqual(duplicate.nome, 'Copia de TR')
        self.assertEqual(duplicate.numero_processo, self.termo.numero_processo)
        self.assertEqual(duplicate.sessoes.count(), 2)
        new_sessao = duplicate.sessoes.get(ordem=1)
        new_item = new_sessao.itens.get(parent=None, texto='Item original')
        self.assertNotEqual(new_item.pk, item.pk)
        self.assertEqual(new_item.filhos.get().texto, child.texto)
        self.assertEqual(new_item.tabela_linhas.get().descricao, 'Notebook')

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

    def test_duplicar_tr_pela_listagem_volta_para_tr_duplicado(self):
        User = get_user_model()
        User.objects.create_superuser(username='admin', password='123')
        self.client.login(username='admin', password='123')
        ItemTR.objects.create(sessao=self.sessao, texto='Item original', ordem=1)

        response = self.client.post(reverse('licitacoes:tr_duplicate', args=[self.termo.pk]))

        duplicate = TermoReferencia.objects.get(nome='Copia de TR')
        self.assertEqual(duplicate.sessoes.get().itens.get().texto, 'Item original')
        self.assertRedirects(
            response,
            reverse('licitacoes:tr_detail', args=[duplicate.pk]),
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
