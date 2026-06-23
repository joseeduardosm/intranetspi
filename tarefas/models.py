# Criado por OpenAI Codex em 23/06/2026
# Define tarefas pessoais com histórico cronológico, comentários e anexos pesquisáveis.

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class TarefaQuerySet(models.QuerySet):
    """Agrupa filtros reutilizados das listagens do módulo."""

    def do_usuario(self, user):
        """Limita o universo pessoal às tarefas criadas por ou atribuídas ao usuário."""

        return self.filter(models.Q(criado_por=user) | models.Q(responsavel=user)).distinct()

    def operacionais(self):
        """Retorna somente tarefas que participam da fila operacional principal."""

        return self.exclude(status=Tarefa.Status.ARQUIVADA)


class Tarefa(models.Model):
    """Representa a tarefa principal cadastrada pelo próprio usuário."""

    class Prioridade(models.TextChoices):
        BAIXA = "BAIXA", "Baixa"
        NORMAL = "NORMAL", "Normal"
        ALTA = "ALTA", "Alta"
        CRITICA = "CRITICA", "Crítica"

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        ARQUIVADA = "ARQUIVADA", "Arquivada"

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tarefas_criadas",
        verbose_name="Criado por",
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tarefas_responsavel",
        verbose_name="Responsável",
    )
    titulo = models.CharField("Título", max_length=200)
    descricao = models.TextField("Descrição")
    prazo = models.DateTimeField("Prazo")
    prioridade = models.CharField("Prioridade", max_length=20, choices=Prioridade.choices, default=Prioridade.NORMAL)
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.PENDENTE)
    concluida_em = models.DateTimeField("Concluída em", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    objects = TarefaQuerySet.as_manager()

    class Meta:
        ordering = ["prazo", "-criado_em", "-id"]
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"

    def __str__(self):
        return f"#{self.pk} - {self.titulo}"

    @property
    def pode_arquivar_automaticamente(self):
        """Indica se a tarefa já atingiu a janela para arquivamento automático."""

        if self.status != self.Status.CONCLUIDA or not self.concluida_em:
            return False
        return self.concluida_em <= timezone.now() - timedelta(days=3)

    def permite_edicao_por(self, user):
        """Permite edição quando o usuário é o criador ou o responsável atual."""

        return bool(user and user.is_authenticated and user.id in {self.criado_por_id, self.responsavel_id})


class TarefaHistorico(models.Model):
    """Mantém a linha do tempo completa e pesquisável do universo da tarefa."""

    class TipoEvento(models.TextChoices):
        CRIACAO = "CRIACAO", "Criação"
        EDICAO = "EDICAO", "Edição"
        ALTERACAO_PRAZO = "ALTERACAO_PRAZO", "Alteração de prazo"
        ALTERACAO_STATUS = "ALTERACAO_STATUS", "Alteração de status"
        CONCLUSAO = "CONCLUSAO", "Conclusão"
        REABERTURA = "REABERTURA", "Reabertura"
        ARQUIVAMENTO_AUTOMATICO = "ARQUIVAMENTO_AUTOMATICO", "Arquivamento automático"
        COMENTARIO = "COMENTARIO", "Comentário"
        ANEXO = "ANEXO", "Anexo"

    tarefa = models.ForeignKey(Tarefa, on_delete=models.CASCADE, related_name="historico", verbose_name="Tarefa")
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tarefas_historicos",
        verbose_name="Autor",
    )
    tipo_evento = models.CharField("Tipo de evento", max_length=32, choices=TipoEvento.choices)
    titulo_evento = models.CharField("Título do evento", max_length=200)
    descricao_evento = models.TextField("Descrição do evento", blank=True)
    comentario = models.TextField("Comentário", blank=True)
    arquivo = models.FileField("Arquivo", upload_to="tarefas/historico/", blank=True)
    nome_arquivo = models.CharField("Nome do arquivo", max_length=255, blank=True)
    prazo_anterior = models.DateTimeField("Prazo anterior", null=True, blank=True)
    prazo_novo = models.DateTimeField("Prazo novo", null=True, blank=True)
    criado_em = models.DateTimeField("Criado em", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "Histórico da tarefa"
        verbose_name_plural = "Históricos das tarefas"

    def __str__(self):
        return f"{self.get_tipo_evento_display()} - Tarefa #{self.tarefa_id}"
