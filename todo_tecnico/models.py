# Criado por OpenAI Codex em 19/06/2026
# Objetivo: Definir o registro mínimo de tarefas técnicas usado como backlog compartilhado.

from django.conf import settings
from django.db import models
from django.utils import timezone


class TarefaTecnicaQuerySet(models.QuerySet):
    """Agrupa filtros recorrentes para manter views e testes mais legíveis."""

    def abertas(self):
        """Retorna tarefas ainda não concluídas."""

        return self.filter(concluido_em__isnull=True)

    def concluidas(self):
        """Retorna tarefas concluídas com data de fechamento preenchida."""

        return self.filter(concluido_em__isnull=False)


class TarefaTecnica(models.Model):
    """Representa uma pendência técnica simples compartilhada pelo time."""

    descricao = models.TextField("Descrição")
    titulo = models.TextField("Título", blank=True)
    solucao = models.TextField("Solução", blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tarefas_tecnicas_criadas",
        verbose_name="Criado por",
    )
    criado_em = models.DateTimeField("Data de inserção", auto_now_add=True)
    concluido_em = models.DateTimeField("Data de conclusão", null=True, blank=True)
    atualizado_em = models.DateTimeField("Última atualização", auto_now=True)

    objects = TarefaTecnicaQuerySet.as_manager()

    class Meta:
        ordering = ["concluido_em", "-criado_em", "-id"]
        verbose_name = "Tarefa técnica"
        verbose_name_plural = "Tarefas técnicas"

    def __str__(self):
        # O título basta para identificar a tarefa em listagens e mensagens do sistema.
        return (self.titulo or self.descricao or self.solucao or f"Tarefa #{self.pk}").strip()

    @property
    def esta_concluida(self) -> bool:
        """Indica o estado derivado da tarefa sem precisar de um campo status."""

        return self.concluido_em is not None


class CodexConfiguracao(models.Model):
    """Mantém parâmetros reutilizáveis do executor automático do Codex."""

    codex_path = models.CharField("Caminho do Codex CLI", max_length=255, default="/root/.local/bin/codex")
    codex_home = models.CharField("Diretório CODEX_HOME", max_length=255, default="/root/.codex")
    workspace_path = models.CharField("Diretório de trabalho", max_length=255, default="/root/aplicacoesspi")
    modelo = models.CharField("Modelo padrão", max_length=120, default="gpt-5.4")
    sandbox = models.CharField("Sandbox do Codex", max_length=60, default="workspace-write")
    habilitar_busca_web = models.BooleanField("Habilitar busca web", default=True)
    timeout_minutos = models.PositiveIntegerField("Tempo máximo por execução (minutos)", default=90)
    limite_tokens_5h = models.PositiveIntegerField("Limite de tokens em 5 horas", default=250000)
    limite_tokens_semanal = models.PositiveIntegerField("Limite semanal de tokens", default=1500000)
    nome_servico = models.CharField("Serviço para reinício", max_length=120, default="aplicacoesspi")
    instrucoes_fixas = models.TextField(
        "Instruções fixas do Codex",
        default=(
            "Melhore o título da tarefa ou crie um título adequado quando ela estiver fraca ou vazia.\n"
            "Preencha a solução com um texto breve, mas elucidativo.\n"
            "Todo código gerado deve ser comentado de forma explicativa, sem excesso.\n"
            "Evite testes excessivos para economizar tokens, mas preserve a segurança da alteração.\n"
            "Não conclua a tarefa deixando a aplicação quebrada, inconsistente ou com erros."
        ),
    )
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        verbose_name = "Configuração do Codex"
        verbose_name_plural = "Configurações do Codex"

    def __str__(self) -> str:
        return "Configuração do Codex"

    @classmethod
    def get_solo(cls):
        """Garante um único registro de configuração para simplificar a interface."""

        configuracao, _created = cls.objects.get_or_create(pk=1)
        return configuracao


class CodexExecucao(models.Model):
    """Representa uma solicitação de execução automática do Codex para uma tarefa técnica."""

    TIPO_MANUAL = "manual"
    TIPO_AGENDADA = "agendada"
    TIPOS = (
        (TIPO_MANUAL, "Manual"),
        (TIPO_AGENDADA, "Agendada"),
    )

    STATUS_AGENDADA = "agendada"
    STATUS_NA_FILA = "na_fila"
    STATUS_EM_EXECUCAO = "em_execucao"
    STATUS_CONCLUIDA = "concluida"
    STATUS_ERRO = "erro"
    STATUS_CANCELADA = "cancelada"
    STATUS_CHOICES = (
        (STATUS_AGENDADA, "Agendada"),
        (STATUS_NA_FILA, "Na fila"),
        (STATUS_EM_EXECUCAO, "Em execução"),
        (STATUS_CONCLUIDA, "Concluída"),
        (STATUS_ERRO, "Erro"),
        (STATUS_CANCELADA, "Cancelada"),
    )

    tarefa = models.ForeignKey(
        TarefaTecnica,
        on_delete=models.CASCADE,
        related_name="execucoes_codex",
        verbose_name="Tarefa",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="execucoes_codex_criadas",
        verbose_name="Criado por",
    )
    tipo = models.CharField("Tipo", max_length=20, choices=TIPOS, default=TIPO_MANUAL)
    status = models.CharField("Status", max_length=20, choices=STATUS_CHOICES, default=STATUS_NA_FILA)
    agendado_para = models.DateTimeField("Agendado para", null=True, blank=True)
    iniciado_em = models.DateTimeField("Iniciado em", null=True, blank=True)
    finalizado_em = models.DateTimeField("Finalizado em", null=True, blank=True)
    prompt_enviado = models.TextField("Prompt enviado", blank=True)
    resposta_final = models.TextField("Resposta final", blank=True)
    resumo_execucao = models.TextField("Resumo da execução", blank=True)
    solucao_gerada = models.TextField("Solução gerada", blank=True)
    titulo_gerado = models.TextField("Título gerado", blank=True)
    log_resumido = models.TextField("Log resumido", blank=True)
    log_completo = models.TextField("Log completo", blank=True)
    saida_pos_execucao = models.TextField("Saída pós-execução", blank=True)
    erro_detalhe = models.TextField("Erro detalhado", blank=True)
    thread_id = models.CharField("Thread do Codex", max_length=120, blank=True)
    input_tokens = models.PositiveIntegerField("Tokens de entrada", default=0)
    cached_input_tokens = models.PositiveIntegerField("Tokens de entrada em cache", default=0)
    output_tokens = models.PositiveIntegerField("Tokens de saída", default=0)
    reasoning_output_tokens = models.PositiveIntegerField("Tokens de raciocínio", default=0)
    total_tokens = models.PositiveIntegerField("Total de tokens", default=0)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        ordering = ["status", "agendado_para", "-criado_em", "-id"]
        verbose_name = "Execução do Codex"
        verbose_name_plural = "Execuções do Codex"

    def __str__(self) -> str:
        return f"Execução Codex #{self.pk} da tarefa #{self.tarefa_id}"

    @property
    def status_legivel(self) -> str:
        return self.get_status_display()

    @property
    def aguardando_processamento(self) -> bool:
        return self.status in {self.STATUS_AGENDADA, self.STATUS_NA_FILA, self.STATUS_EM_EXECUCAO}

    def promover_para_fila(self) -> None:
        """Converte execuções agendadas vencidas para a fila pronta de processamento."""

        if self.status == self.STATUS_AGENDADA and self.agendado_para and self.agendado_para <= timezone.now():
            self.status = self.STATUS_NA_FILA
