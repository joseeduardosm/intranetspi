# Criado por OpenAI Codex em 23/06/2026
# Valida dashboard pessoal, status, progresso temporal e arquivamento do módulo de tarefas.

from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from acls.models import Recurso, RegraAcesso
from setores.models import SetorNode, UserSetorMembership
from tarefas.forms import SuperiorImediatoForm
from tarefas.models import Tarefa, TarefaHistorico
from tarefas.services import (
    arquivar_tarefas_concluidas,
    calcular_progresso_prazo_tarefa,
    calcular_resumo_carga_usuario,
    gestor_tem_visao_gerencial,
    mover_tarefa_status,
    resolver_escopo_gerencial,
)


User = get_user_model()


def aware_dt(year, month, day, hour=9, minute=0):
    """Cria datas timezone-aware para os cenários do módulo."""

    return timezone.make_aware(datetime(year, month, day, hour, minute), timezone.get_current_timezone())


class TarefasBaseTestCase(TestCase):
    """Monta usuários com ACL válida para o novo módulo."""

    def setUp(self):
        self.usuario = User.objects.create_user(username="usuario-tarefas", password="123", email="u@spi.sp.gov.br")
        self.superior = User.objects.create_user(username="superior-tarefas", password="123", email="s@spi.sp.gov.br")
        self.outro = User.objects.create_user(username="outro-tarefas", password="123", email="o@spi.sp.gov.br")
        for user, nome in (
            (self.usuario, "Usuário Tarefas"),
            (self.superior, "Superior Tarefas"),
            (self.outro, "Outro Usuário"),
        ):
            perfil = user.perfil
            perfil.nome_completo = nome
            perfil.ramal = "1000"
            perfil.cargo = "Analista"
            perfil.setor = "Setor"
            perfil.andar = "1"
            perfil.bloco = "A"
            perfil.save()
        self.usuario.perfil.superior_imediato = self.superior
        self.usuario.perfil.save(update_fields=["superior_imediato", "atualizado_em"])
        self.superior.perfil.superior_imediato = self.outro
        self.superior.perfil.save(update_fields=["superior_imediato", "atualizado_em"])
        grupo_diretoria = Group.objects.create(name="Diretoria Teste")
        grupo_coordenacao = Group.objects.create(name="Coordenacao Teste")
        grupo_setor = Group.objects.create(name="Setor Teste")
        self.setor_diretoria = SetorNode.objects.create(group=grupo_diretoria, lider=self.superior)
        self.setor_coordenacao = SetorNode.objects.create(group=grupo_coordenacao, parent=self.setor_diretoria, lider=self.superior)
        self.setor_time = SetorNode.objects.create(group=grupo_setor, parent=self.setor_coordenacao)
        UserSetorMembership.objects.create(user=self.superior, setor=self.setor_coordenacao)
        UserSetorMembership.objects.create(user=self.usuario, setor=self.setor_time)
        UserSetorMembership.objects.create(user=self.outro, setor=self.setor_time)
        recurso, _ = Recurso.objects.get_or_create(
            slug="tarefas",
            defaults={"nome": "Tarefas", "descricao": "Módulo de tarefas", "url_base": "/tarefas/"},
        )
        for user in (self.usuario, self.superior, self.outro):
            regra = RegraAcesso.objects.create(recurso=recurso, nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL)
            regra.usuarios.add(user)

    def criar_tarefa(self, **kwargs):
        dados = {
            "criado_por": self.usuario,
            "responsavel": self.usuario,
            "titulo": "Tarefa base",
            "descricao": "Descrição base",
            "prazo": aware_dt(2026, 6, 30),
            "prioridade": Tarefa.Prioridade.NORMAL,
            "status": Tarefa.Status.PENDENTE,
        }
        dados.update(kwargs)
        return Tarefa.objects.create(**dados)


class TarefasFluxoTests(TarefasBaseTestCase):
    """Cobre onboarding, dashboard, detalhe e movimentação do fluxo."""

    def test_primeiro_acesso_sem_superior_redireciona_para_onboarding(self):
        outro = User.objects.create_user(username="sem-superior", password="123", email="sem@spi.sp.gov.br")
        regra = RegraAcesso.objects.create(recurso=Recurso.objects.get(slug="tarefas"), nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL)
        regra.usuarios.add(outro)
        self.client.login(username="sem-superior", password="123")
        response = self.client.get(reverse("tarefas:list"))
        self.assertRedirects(response, reverse("tarefas:onboarding"))

    def test_onboarding_exibe_nome_completo_no_seletor_de_superior(self):
        form = SuperiorImediatoForm(instance=self.outro.perfil, current_user=self.outro)
        self.assertEqual(form.fields["superior_imediato"].label_from_instance(self.superior), "Superior Tarefas")

    def test_criar_tarefa_define_autor_e_responsavel(self):
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.post(
            reverse("tarefas:create"),
            {
                "titulo": "Preparar ofício",
                "descricao": "Detalhar a demanda.",
                "prazo": "2026-06-30T10:00",
                "prioridade": Tarefa.Prioridade.ALTA,
            },
        )
        tarefa = Tarefa.objects.get(titulo="Preparar ofício")
        self.assertRedirects(response, reverse("tarefas:detail", args=[tarefa.pk]))
        self.assertEqual(tarefa.criado_por, self.usuario)
        self.assertEqual(tarefa.responsavel, self.usuario)
        self.assertEqual(tarefa.status, Tarefa.Status.PENDENTE)
        self.assertEqual(tarefa.historico.count(), 1)

    def test_gestor_com_liderados_ve_aba_equipe(self):
        self.client.login(username="superior-tarefas", password="123")
        response = self.client.get(reverse("tarefas:list"), {"dashboard": "team", "scope": "imediatos"})
        self.assertContains(response, "Minha equipe")
        self.assertContains(response, "Usuário Tarefas")

    def test_usuario_sem_liderados_nao_acessa_visao_gerencial(self):
        self.client.login(username="outro-tarefas", password="123")
        response = self.client.get(reverse("tarefas:list"), {"dashboard": "team", "scope": "imediatos"})
        self.assertEqual(response.status_code, 403)

    def test_detalhe_gerencial_da_pessoa_mostra_tarefas_dela(self):
        tarefa = self.criar_tarefa(responsavel=self.usuario, criado_por=self.superior, titulo="Tarefa do liderado")
        self.client.login(username="superior-tarefas", password="123")
        response = self.client.get(reverse("tarefas:team_person", args=[self.usuario.pk]))
        self.assertContains(response, "Tarefas da pessoa")
        self.assertContains(response, "Tarefa do liderado")
        self.assertContains(response, reverse("tarefas:detail", args=[tarefa.pk]))

    def test_gestor_consegue_abrir_detalhe_da_tarefa_do_liderado(self):
        tarefa = self.criar_tarefa(responsavel=self.usuario, criado_por=self.usuario, titulo="Tarefa visível ao gestor")
        self.client.login(username="superior-tarefas", password="123")
        response = self.client.get(reverse("tarefas:detail", args=[tarefa.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tarefa visível ao gestor")

    def test_listagem_tabela_mostra_autor_responsavel_e_arquivada_por_filtro(self):
        self.client.login(username="usuario-tarefas", password="123")
        self.criar_tarefa(titulo="Operacional")
        self.criar_tarefa(titulo="Arquivada", status=Tarefa.Status.ARQUIVADA)
        response = self.client.get(reverse("tarefas:list"), {"status": "ARQUIVADA", "view": "table"})
        self.assertContains(response, "Arquivada")
        self.assertContains(response, "Usuário Tarefas")
        self.assertContains(response, "Atribuído")

    def test_listagem_ordenacao_por_titulo_desc(self):
        self.client.login(username="usuario-tarefas", password="123")
        self.criar_tarefa(titulo="Alpha")
        self.criar_tarefa(titulo="Zulu")
        response = self.client.get(reverse("tarefas:list"), {"order_by": "titulo", "direction": "desc"})
        conteudo = response.content.decode("utf-8")
        self.assertLess(conteudo.index("Zulu"), conteudo.index("Alpha"))

    def test_kanban_exibe_somente_status_operacionais(self):
        self.client.login(username="usuario-tarefas", password="123")
        self.criar_tarefa(titulo="Pendente", status=Tarefa.Status.PENDENTE)
        self.criar_tarefa(titulo="Concluída", status=Tarefa.Status.CONCLUIDA)
        arquivada = self.criar_tarefa(titulo="Arquivada", status=Tarefa.Status.ARQUIVADA)
        response = self.client.get(reverse("tarefas:list"), {"view": "kanban"})
        self.assertContains(response, "Pendente")
        self.assertContains(response, "Concluída")
        self.assertNotContains(response, f"#{arquivada.pk} {arquivada.titulo}")

    def test_detalhe_exibe_autor_responsavel_e_filtros_de_historico(self):
        tarefa = self.criar_tarefa()
        TarefaHistorico.objects.create(
            tarefa=tarefa,
            autor=self.usuario,
            tipo_evento=TarefaHistorico.TipoEvento.COMENTARIO,
            titulo_evento="Comentário adicionado",
            comentario="Texto filtrável",
        )
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.get(reverse("tarefas:detail", args=[tarefa.pk]), {"tipo": "COMENTARIOS"})
        self.assertContains(response, "Autor")
        self.assertContains(response, "Atribuído")
        self.assertContains(response, "Texto filtrável")

    def test_detalhe_permite_comentario_e_anexo(self):
        tarefa = self.criar_tarefa()
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.post(
            reverse("tarefas:historico_create", args=[tarefa.pk]),
            {
                "comentario": "Comentário com arquivo",
                "arquivo": SimpleUploadedFile("evidencia.txt", b"conteudo"),
            },
        )
        self.assertRedirects(response, reverse("tarefas:detail", args=[tarefa.pk]))
        self.assertEqual(TarefaHistorico.objects.filter(tarefa=tarefa).count(), 1)

    def test_alterar_prazo_registra_justificativa(self):
        tarefa = self.criar_tarefa()
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.post(
            reverse("tarefas:update_prazo", args=[tarefa.pk]),
            {"prazo": "2026-07-02T11:30", "justificativa": "Necessário ajustar o prazo."},
        )
        self.assertRedirects(response, reverse("tarefas:detail", args=[tarefa.pk]))
        evento = TarefaHistorico.objects.filter(tarefa=tarefa, tipo_evento=TarefaHistorico.TipoEvento.ALTERACAO_PRAZO).latest("id")
        self.assertIn("Necessário ajustar o prazo.", evento.descricao_evento)

    def test_busca_macro_considera_autor_responsavel_e_historico(self):
        tarefa = self.criar_tarefa(titulo="Tarefa especial", responsavel=self.outro)
        TarefaHistorico.objects.create(
            tarefa=tarefa,
            autor=self.usuario,
            tipo_evento=TarefaHistorico.TipoEvento.COMENTARIO,
            titulo_evento="Comentário adicionado",
            comentario="Texto macro pesquisável",
        )
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.get(reverse("tarefas:list"), {"q": "Texto macro pesquisável"})
        self.assertContains(response, "Tarefa especial")
        response = self.client.get(reverse("tarefas:list"), {"q": "Outro Usuário"})
        self.assertContains(response, "Tarefa especial")

    def test_ajax_move_kanban_conclui_tarefa(self):
        tarefa = self.criar_tarefa(status=Tarefa.Status.EM_ANDAMENTO)
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.post(
            reverse("tarefas:update_status", args=[tarefa.pk]),
            {"status": Tarefa.Status.CONCLUIDA},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        tarefa.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tarefa.status, Tarefa.Status.CONCLUIDA)
        self.assertIsNotNone(tarefa.concluida_em)

    def test_ajax_reabre_tarefa_concluida(self):
        tarefa = self.criar_tarefa(status=Tarefa.Status.CONCLUIDA, concluida_em=timezone.now())
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.post(
            reverse("tarefas:update_status", args=[tarefa.pk]),
            {"status": Tarefa.Status.PENDENTE},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        tarefa.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(tarefa.status, Tarefa.Status.PENDENTE)
        self.assertIsNone(tarefa.concluida_em)

    def test_ajax_recusa_movimento_de_arquivada(self):
        tarefa = self.criar_tarefa(status=Tarefa.Status.ARQUIVADA)
        self.client.login(username="usuario-tarefas", password="123")
        response = self.client.post(
            reverse("tarefas:update_status", args=[tarefa.pk]),
            {"status": Tarefa.Status.PENDENTE},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)


class TarefasServicoTests(TarefasBaseTestCase):
    """Valida cálculo temporal, carga e arquivamento automático."""

    def test_motor_de_carga_aplica_pesos_e_faixa_do_documento(self):
        referencia = aware_dt(2026, 6, 23, 9, 0)
        self.criar_tarefa(titulo="Crítica atrasada", prazo=aware_dt(2026, 6, 22, 9, 0), prioridade=Tarefa.Prioridade.CRITICA)
        self.criar_tarefa(titulo="Alta para a semana", prazo=aware_dt(2026, 6, 28, 9, 0), prioridade=Tarefa.Prioridade.ALTA)
        self.criar_tarefa(titulo="Baixa folgada", prazo=aware_dt(2026, 7, 20, 9, 0), prioridade=Tarefa.Prioridade.BAIXA)
        with patch("tarefas.services.timezone.now", return_value=referencia):
            resumo = calcular_resumo_carga_usuario(Tarefa.objects.do_usuario(self.usuario))
        self.assertEqual(resumo["atrasadas"], 1)
        self.assertEqual(resumo["carga_total"], 43)
        self.assertEqual(resumo["faixa_ocupacao"]["rotulo"], "Alta ocupação")

    def test_calculo_progresso_recem_criada(self):
        tarefa = self.criar_tarefa(prazo=timezone.now() + timedelta(days=10))
        progresso = calcular_progresso_prazo_tarefa(tarefa, referencia=tarefa.criado_em)
        self.assertEqual(progresso["percentual"], 0)
        self.assertEqual(progresso["cor"], "success")

    def test_calculo_progresso_faixas(self):
        base = timezone.now() - timedelta(days=5)
        tarefa = self.criar_tarefa(prazo=base + timedelta(days=10))
        tarefa.criado_em = base
        tarefa.save(update_fields=["criado_em"])
        progresso = calcular_progresso_prazo_tarefa(tarefa, referencia=base + timedelta(days=5, hours=1))
        self.assertEqual(progresso["cor"], "warning")

        tarefa2 = self.criar_tarefa(titulo="Outra", prazo=base + timedelta(days=10))
        tarefa2.criado_em = base
        tarefa2.save(update_fields=["criado_em"])
        progresso2 = calcular_progresso_prazo_tarefa(tarefa2, referencia=base + timedelta(days=8))
        self.assertEqual(progresso2["cor"], "danger")

    def test_calculo_progresso_vencida(self):
        base = timezone.now() - timedelta(days=6)
        tarefa = self.criar_tarefa(prazo=base + timedelta(days=2))
        tarefa.criado_em = base
        tarefa.save(update_fields=["criado_em"])
        progresso = calcular_progresso_prazo_tarefa(tarefa, referencia=base + timedelta(days=3))
        self.assertTrue(progresso["atrasada"])
        self.assertEqual(progresso["cor"], "danger-strong")

    def test_arquivamento_automatico_servico(self):
        tarefa = self.criar_tarefa(status=Tarefa.Status.CONCLUIDA, concluida_em=timezone.now() - timedelta(days=4))
        total = arquivar_tarefas_concluidas()
        tarefa.refresh_from_db()
        self.assertEqual(total, 1)
        self.assertEqual(tarefa.status, Tarefa.Status.ARQUIVADA)
        self.assertTrue(
            TarefaHistorico.objects.filter(
                tarefa=tarefa,
                tipo_evento=TarefaHistorico.TipoEvento.ARQUIVAMENTO_AUTOMATICO,
            ).exists()
        )

    def test_reabertura_antes_do_arquivamento_limpa_conclusao(self):
        tarefa = self.criar_tarefa(status=Tarefa.Status.CONCLUIDA, concluida_em=timezone.now() - timedelta(days=2))
        mover_tarefa_status(tarefa=tarefa, novo_status=Tarefa.Status.EM_ANDAMENTO, autor=self.usuario)
        tarefa.refresh_from_db()
        self.assertEqual(tarefa.status, Tarefa.Status.EM_ANDAMENTO)
        self.assertIsNone(tarefa.concluida_em)

    def test_command_arquiva_tarefas(self):
        self.criar_tarefa(status=Tarefa.Status.CONCLUIDA, concluida_em=timezone.now() - timedelta(days=4))
        stdout = StringIO()
        call_command("arquivar_tarefas_concluidas", stdout=stdout)
        self.assertIn("1 tarefa(s) arquivada(s) automaticamente.", stdout.getvalue())

    def test_servico_indica_gestor_com_visao_gerencial(self):
        self.assertTrue(gestor_tem_visao_gerencial(self.superior))
        self.assertFalse(gestor_tem_visao_gerencial(self.outro))

    def test_escopo_imediatos_mostra_somente_primeiro_nivel(self):
        neto = User.objects.create_user(username="neto-tarefas", password="123", email="n@spi.sp.gov.br")
        neto.perfil.nome_completo = "Neto Tarefas"
        neto.perfil.ramal = "1001"
        neto.perfil.cargo = "Assistente"
        neto.perfil.setor = "Setor"
        neto.perfil.andar = "1"
        neto.perfil.bloco = "A"
        neto.perfil.superior_imediato = self.usuario
        neto.perfil.save()
        regra = RegraAcesso.objects.create(recurso=Recurso.objects.get(slug="tarefas"), nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL)
        regra.usuarios.add(neto)
        scope = resolver_escopo_gerencial(self.superior, "imediatos")
        self.assertEqual([usuario.username for usuario in scope["usuarios"]], ["usuario-tarefas"])

    def test_escopo_arvore_inclui_niveis_abaixo_sem_duplicidade(self):
        neto = User.objects.create_user(username="neto-arvore", password="123", email="na@spi.sp.gov.br")
        neto.perfil.nome_completo = "Neto Árvore"
        neto.perfil.ramal = "1002"
        neto.perfil.cargo = "Assistente"
        neto.perfil.setor = "Setor"
        neto.perfil.andar = "1"
        neto.perfil.bloco = "A"
        neto.perfil.superior_imediato = self.usuario
        neto.perfil.save()
        regra = RegraAcesso.objects.create(recurso=Recurso.objects.get(slug="tarefas"), nivel=RegraAcesso.NIVEL_CONTROLE_TOTAL)
        regra.usuarios.add(neto)
        scope = resolver_escopo_gerencial(self.superior, "arvore")
        usernames = sorted(usuario.username for usuario in scope["usuarios"])
        self.assertEqual(usernames, ["neto-arvore", "usuario-tarefas"])

    def test_escopo_setor_usa_arvore_de_setores(self):
        scope = resolver_escopo_gerencial(self.superior, "setor")
        usernames = sorted(usuario.username for usuario in scope["usuarios"])
        self.assertEqual(usernames, ["outro-tarefas", "usuario-tarefas"])
