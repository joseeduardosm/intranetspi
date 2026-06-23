# Criado por OpenAI Codex em 19/06/2026
# Objetivo: Validar o fluxo simplificado do backlog técnico, ACL e filtros da listagem.

from datetime import timedelta
import sqlite3
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.forms import Textarea
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acls.models import Recurso, RegraAcesso

from .forms import (
    CodexAgendamentoForm,
    CodexConfiguracaoForm,
    TarefaTecnicaCadastroForm,
    TarefaTecnicaEdicaoConcluidaForm,
    TarefaTecnicaSolucaoForm,
)
from .models import CodexConfiguracao, CodexExecucao, TarefaTecnica
from .services import normalizar_titulo_tarefa, obter_monitoramento_codex


User = get_user_model()


class TodoTecnicoBaseTestCase(TestCase):
    """Prepara usuários e regras ACL compatíveis com o padrão do projeto."""

    def setUp(self):
        self.recurso, _created = Recurso.objects.get_or_create(
            slug="todo_tecnico",
            defaults={"nome": "To-Do Técnico", "url_base": "/todo-tecnico/"},
        )
        self.root = User.objects.create_user(username="root", password="123", first_name="Root", is_staff=True, is_superuser=True)
        self.leitor = User.objects.create_user(username="leitor", password="123", first_name="Lia")
        self.autor = User.objects.create_user(username="autor", password="123", first_name="Ana")
        self.outro = User.objects.create_user(username="outro", password="123", first_name="Bruno")
        self.admin = User.objects.create_user(username="admin", password="123", is_staff=True)

        regra_total = RegraAcesso.objects.create(
            recurso=self.recurso,
            nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL,
        )
        regra_total.usuarios.add(self.root)

    def criar_tarefa(self, **kwargs):
        """Monta tarefas com defaults simples para reduzir ruído nos cenários."""

        dados = {
            "titulo": "Corrigir integração LDAP",
            "descricao": "A autenticação LDAP falha para parte dos usuários.",
            "criado_por": self.autor,
        }
        dados.update(kwargs)
        return TarefaTecnica.objects.create(**dados)


class TarefaTecnicaModelTests(TodoTecnicoBaseTestCase):
    """Cobre o comportamento derivado do estado da tarefa."""

    def test_tarefa_inicia_aberta_e_pode_ser_consultada_como_concluida(self):
        tarefa = self.criar_tarefa()
        self.assertFalse(tarefa.esta_concluida)
        tarefa.concluido_em = timezone.now()
        tarefa.save(update_fields=["concluido_em", "atualizado_em"])
        tarefa.refresh_from_db()
        self.assertTrue(tarefa.esta_concluida)

    def test_formulario_usa_textarea_para_o_titulo(self):
        form = TarefaTecnicaCadastroForm()
        self.assertIsInstance(form.fields["descricao"].widget, Textarea)

    def test_formulario_de_solucao_exige_preenchimento(self):
        form = TarefaTecnicaSolucaoForm(data={"solucao": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("solucao", form.errors)

    def test_normaliza_titulo_quando_tarefa_nao_tem_resumo(self):
        tarefa = self.criar_tarefa(titulo="", descricao="corrigir espaçamento do cabeçalho\nsegunda linha")
        self.assertEqual(normalizar_titulo_tarefa(tarefa), "Corrigir espaçamento do cabeçalho")

    def test_formulario_de_agendamento_exige_data_futura(self):
        form = CodexAgendamentoForm(data={"agendado_para": "2000-01-01T10:00"})
        self.assertFalse(form.is_valid())
        self.assertIn("agendado_para", form.errors)

    def test_formulario_de_configuracao_do_codex_expoe_instrucao_fixa(self):
        form = CodexConfiguracaoForm(instance=CodexConfiguracao.get_solo())
        self.assertIn("instrucoes_fixas", form.fields)


class TodoTecnicoAclTests(TodoTecnicoBaseTestCase):
    """Valida a restrição adicional do módulo ao usuário root."""

    def test_root_acessa_listagem(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Backlog técnico")

    def test_root_cria_tarefa(self):
        self.client.login(username="root", password="123")
        response = self.client.post(
            reverse("todo_tecnico:create"),
            {"titulo": "Ajustar CSS do módulo", "descricao": "Corrigir o espaçamento da tabela principal."},
        )
        self.assertEqual(response.status_code, 302)
        tarefa = TarefaTecnica.objects.get(titulo="Ajustar CSS do módulo")
        self.assertEqual(tarefa.criado_por, self.root)
        self.assertEqual(tarefa.descricao, "Corrigir o espaçamento da tabela principal.")

    def test_usuario_com_acl_nao_root_recebe_403(self):
        self.client.login(username="autor", password="123")
        response = self.client.get(reverse("todo_tecnico:list"))
        self.assertEqual(response.status_code, 403)

    def test_staff_nao_root_recebe_403(self):
        self.client.login(username="admin", password="123")
        response = self.client.get(reverse("todo_tecnico:list"))
        self.assertEqual(response.status_code, 403)

    def test_root_edita_qualquer_tarefa(self):
        tarefa = self.criar_tarefa(criado_por=self.autor)
        self.client.login(username="root", password="123")
        response = self.client.post(
            reverse("todo_tecnico:update", args=[tarefa.pk]),
            {"titulo": "Título ajustado", "descricao": "Descrição ajustada"},
        )
        self.assertEqual(response.status_code, 302)
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.titulo, "Título ajustado")
        self.assertEqual(tarefa.descricao, "Descrição ajustada")

    def test_formulario_de_abertura_nao_exibe_solucao(self):
        tarefa = self.criar_tarefa(criado_por=self.root)
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:update", args=[tarefa.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="solucao"', html=False)

    def test_tarefa_concluida_exibe_campo_solucao_ao_editar(self):
        tarefa = self.criar_tarefa(criado_por=self.root, concluido_em=timezone.now(), solucao="Correção aplicada.")
        self.client.login(username="root", password="123")

        response = self.client.get(reverse("todo_tecnico:update", args=[tarefa.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="solucao"', html=False)
        self.assertContains(response, "Correção aplicada.")

    def test_formulario_exibe_atalho_ctrl_enter_para_salvar(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ctrl")
        self.assertContains(response, "requestSubmit")


class TodoTecnicoListagemTests(TodoTecnicoBaseTestCase):
    """Cobre resumo e filtros de situação e autoria."""

    def setUp(self):
        super().setUp()
        self.aberta_autor = self.criar_tarefa(titulo="Tarefa aberta do autor")
        self.aberta_outro = self.criar_tarefa(titulo="Tarefa aberta do outro", criado_por=self.outro)
        self.concluida = self.criar_tarefa(
            titulo="Tarefa concluída",
            concluido_em=timezone.now() - timedelta(days=1),
        )

    def test_listagem_exibe_contadores(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:list"), {"situacao": "todas"})
        self.assertContains(response, "3")
        self.assertContains(response, f"#{self.aberta_autor.pk}")
        self.assertEqual(response.context["resumo"]["total"], 3)
        self.assertEqual(response.context["resumo"]["abertas"], 2)
        self.assertEqual(response.context["resumo"]["concluidas"], 1)
        self.assertEqual(response.context["resumo"]["minhas_abertas"], 0)

    def test_filtro_de_abertas(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:list"), {"situacao": "abertas"})
        tarefas = list(response.context["tarefas"])
        self.assertEqual(len(tarefas), 2)
        self.assertTrue(all(tarefa.concluido_em is None for tarefa in tarefas))

    def test_filtro_de_concluidas(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:list"), {"situacao": "concluidas"})
        tarefas = list(response.context["tarefas"])
        self.assertEqual(len(tarefas), 1)
        self.assertEqual(tarefas[0].pk, self.concluida.pk)

    def test_filtro_de_minhas_tarefas(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:list"), {"situacao": "todas", "minhas": "1"})
        tarefas = list(response.context["tarefas"])
        self.assertEqual(tarefas, [])

    def test_id_da_tarefa_e_clicavel_para_copiar_identificador(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:list"), {"situacao": "todas"})
        self.assertContains(response, 'data-copy-task-id="tarefa #')
        self.assertContains(response, "navigator.clipboard.writeText")

    def test_listagem_exibe_menu_de_acoes_com_ver_solucionar_e_excluir(self):
        self.client.login(username="root", password="123")

        response = self.client.get(reverse("todo_tecnico:list"), {"situacao": "todas"})

        self.assertContains(response, "todo-tecnico-actions-toggle")
        self.assertContains(response, 'data-bs-toggle="dropdown"', html=False)
        self.assertContains(response, 'data-bs-boundary="viewport"', html=False)
        self.assertContains(response, reverse("todo_tecnico:detail", args=[self.aberta_autor.pk]))
        self.assertContains(response, reverse("todo_tecnico:solve", args=[self.aberta_autor.pk]))
        self.assertContains(response, reverse("todo_tecnico:delete", args=[self.aberta_autor.pk]))
        self.assertNotContains(response, 'btn btn-sm btn-success', html=False)

    def test_listagem_exibe_painel_do_codex_e_acoes_de_execucao(self):
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:list"), {"situacao": "todas"})
        self.assertContains(response, "Monitor de tokens")
        self.assertContains(response, "Codex agendado")
        self.assertContains(response, reverse("todo_tecnico:codex_run", args=[self.aberta_autor.pk]))
        self.assertContains(response, "Configuração do Codex")

    def test_monitoramento_codex_soma_tokens_em_janelas_moveis(self):
        with patch("todo_tecnico.services._consumo_codex_por_threads", return_value=None):
            tarefa = self.criar_tarefa(criado_por=self.root)
            CodexExecucao.objects.create(
                tarefa=tarefa,
                criado_por=self.root,
                status=CodexExecucao.STATUS_CONCLUIDA,
                iniciado_em=timezone.now() - timedelta(hours=1),
                finalizado_em=timezone.now(),
                total_tokens=400,
            )
            configuracao = CodexConfiguracao.get_solo()
            configuracao.limite_tokens_5h = 1000
            configuracao.limite_tokens_semanal = 2000
            configuracao.save()

            monitoramento = obter_monitoramento_codex(configuracao)

        self.assertEqual(monitoramento["janela_5h"].consumido, 400)
        self.assertEqual(monitoramento["janela_5h"].restante, 600)
        self.assertEqual(monitoramento["janela_semanal"].consumido, 400)

    def test_monitoramento_codex_prioriza_tokens_do_state_local_do_cli(self):
        configuracao = CodexConfiguracao.get_solo()
        configuracao.workspace_path = "/tmp/projeto-codex"
        configuracao.limite_tokens_5h = 1000
        configuracao.limite_tokens_semanal = 2000

        with tempfile.TemporaryDirectory() as temp_dir:
            configuracao.codex_home = temp_dir
            configuracao.save()

            conexao = sqlite3.connect(f"{temp_dir}/state_5.sqlite")
            conexao.execute(
                """
                create table threads (
                    id text primary key,
                    rollout_path text not null default '',
                    created_at integer not null,
                    updated_at integer not null,
                    source text not null default '',
                    model_provider text not null default '',
                    cwd text not null,
                    title text not null default '',
                    sandbox_policy text not null default '',
                    approval_mode text not null default '',
                    tokens_used integer not null default 0,
                    has_user_event integer not null default 0,
                    archived integer not null default 0,
                    archived_at integer
                )
                """
            )
            agora = int(timezone.now().timestamp())
            conexao.execute(
                """
                insert into threads (
                    id, rollout_path, created_at, updated_at, source, model_provider, cwd, title,
                    sandbox_policy, approval_mode, tokens_used, has_user_event, archived, archived_at
                ) values (?, '', ?, ?, '', '', ?, '', '', '', ?, 0, 0, null)
                """,
                ["thread-1", agora - 3600, agora - 3500, "/tmp/projeto-codex", 700],
            )
            conexao.commit()
            conexao.close()

            monitoramento = obter_monitoramento_codex(configuracao)

        self.assertEqual(monitoramento["janela_5h"].consumido, 700)
        self.assertEqual(monitoramento["janela_5h"].restante, 300)
        self.assertEqual(monitoramento["janela_semanal"].consumido, 700)
        self.assertIsNotNone(monitoramento["janela_5h"].redefinicao_em)

    def test_monitoramento_codex_considera_thread_aberta_no_diretorio_pai_do_projeto(self):
        configuracao = CodexConfiguracao.get_solo()
        configuracao.workspace_path = "/tmp/projeto-codex/subpasta"
        configuracao.limite_tokens_5h = 1000

        with tempfile.TemporaryDirectory() as temp_dir:
            configuracao.codex_home = temp_dir
            configuracao.save()

            conexao = sqlite3.connect(f"{temp_dir}/state_5.sqlite")
            conexao.execute(
                """
                create table threads (
                    id text primary key,
                    rollout_path text not null default '',
                    created_at integer not null,
                    updated_at integer not null,
                    source text not null default '',
                    model_provider text not null default '',
                    cwd text not null,
                    title text not null default '',
                    sandbox_policy text not null default '',
                    approval_mode text not null default '',
                    tokens_used integer not null default 0,
                    has_user_event integer not null default 0,
                    archived integer not null default 0,
                    archived_at integer
                )
                """
            )
            agora = int(timezone.now().timestamp())
            conexao.execute(
                """
                insert into threads (
                    id, rollout_path, created_at, updated_at, source, model_provider, cwd, title,
                    sandbox_policy, approval_mode, tokens_used, has_user_event, archived, archived_at
                ) values (?, '', ?, ?, '', '', ?, '', '', '', ?, 0, 0, null)
                """,
                ["thread-parent", agora - 1800, agora - 1700, "/tmp/projeto-codex", 500],
            )
            conexao.commit()
            conexao.close()

            monitoramento = obter_monitoramento_codex(configuracao)

        self.assertEqual(monitoramento["janela_5h"].consumido, 500)


class TodoTecnicoAcoesTests(TodoTecnicoBaseTestCase):
    """Confirma as transições de solucionar e reabrir sem usar status explícito."""

    def test_detalhe_exibe_conteudo_completo_da_tarefa(self):
        tarefa = self.criar_tarefa(
            criado_por=self.root,
            solucao="Atualização aplicada com sucesso.",
            concluido_em=timezone.now(),
        )
        self.client.login(username="root", password="123")

        response = self.client.get(reverse("todo_tecnico:detail", args=[tarefa.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, tarefa.descricao)
        self.assertContains(response, tarefa.solucao)
        self.assertContains(response, f"Tarefa #{tarefa.pk}")

    def test_solucionar_preenche_solucao_e_data_de_conclusao(self):
        tarefa = self.criar_tarefa(criado_por=self.root)
        self.client.login(username="root", password="123")
        response = self.client.post(reverse("todo_tecnico:solve", args=[tarefa.pk]), {"solucao": "Ajuste aplicado no formulário."})
        self.assertEqual(response.status_code, 302)
        tarefa.refresh_from_db()
        self.assertIsNotNone(tarefa.concluido_em)
        self.assertEqual(tarefa.solucao, "Ajuste aplicado no formulário.")

    def test_tela_de_solucao_exibe_descricao_mas_nao_titulo_como_obrigatorio(self):
        tarefa = self.criar_tarefa(criado_por=self.root)
        self.client.login(username="root", password="123")
        response = self.client.get(reverse("todo_tecnico:solve", args=[tarefa.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, tarefa.descricao)
        self.assertContains(response, 'name="solucao"', html=False)

    def test_reabrir_limpa_data_de_conclusao(self):
        tarefa = self.criar_tarefa(criado_por=self.root, concluido_em=timezone.now())
        self.client.login(username="root", password="123")
        response = self.client.post(reverse("todo_tecnico:reopen", args=[tarefa.pk]))
        self.assertEqual(response.status_code, 302)
        tarefa.refresh_from_db()
        self.assertIsNone(tarefa.concluido_em)

    def test_excluir_remove_tarefa(self):
        tarefa = self.criar_tarefa(criado_por=self.root)
        self.client.login(username="root", password="123")

        response = self.client.post(reverse("todo_tecnico:delete", args=[tarefa.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(TarefaTecnica.objects.filter(pk=tarefa.pk).exists())

    def test_execucao_manual_do_codex_cria_item_na_fila(self):
        tarefa = self.criar_tarefa(criado_por=self.root)
        self.client.login(username="root", password="123")

        response = self.client.post(reverse("todo_tecnico:codex_run", args=[tarefa.pk]))

        self.assertEqual(response.status_code, 302)
        execucao = CodexExecucao.objects.get(tarefa=tarefa)
        self.assertEqual(execucao.status, CodexExecucao.STATUS_NA_FILA)
        self.assertEqual(execucao.tipo, CodexExecucao.TIPO_MANUAL)

    def test_execucao_agendada_do_codex_grava_data_futura(self):
        tarefa = self.criar_tarefa(criado_por=self.root)
        self.client.login(username="root", password="123")
        futuro = (timezone.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")

        response = self.client.post(reverse("todo_tecnico:codex_schedule", args=[tarefa.pk]), {"agendado_para": futuro})

        self.assertEqual(response.status_code, 302)
        execucao = CodexExecucao.objects.get(tarefa=tarefa)
        self.assertEqual(execucao.status, CodexExecucao.STATUS_AGENDADA)
        self.assertEqual(execucao.tipo, CodexExecucao.TIPO_AGENDADA)
        self.assertIsNotNone(execucao.agendado_para)

    @patch("todo_tecnico.views.disparar_worker_background")
    def test_salvar_configuracao_do_codex(self, _disparar_worker):
        self.client.login(username="root", password="123")
        configuracao = CodexConfiguracao.get_solo()

        response = self.client.post(
            reverse("todo_tecnico:codex_config"),
            {
                "codex_path": configuracao.codex_path,
                "codex_home": configuracao.codex_home,
                "workspace_path": configuracao.workspace_path,
                "modelo": "gpt-5.5",
                "sandbox": configuracao.sandbox,
                "habilitar_busca_web": "on",
                "timeout_minutos": 50,
                "limite_tokens_5h": 1234,
                "limite_tokens_semanal": 5678,
                "nome_servico": configuracao.nome_servico,
                "instrucoes_fixas": "Instruções revisadas.",
            },
        )

        self.assertEqual(response.status_code, 302)
        configuracao.refresh_from_db()
        self.assertEqual(configuracao.modelo, "gpt-5.5")
        self.assertEqual(configuracao.limite_tokens_5h, 1234)
