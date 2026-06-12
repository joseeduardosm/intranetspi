# Criado por OpenAI Codex em 12/06/2026
# Modela mensagens institucionais, destinatários, audiência original e trilha de auditoria.

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from setores.models import SetorNode


class Mensagem(models.Model):
    """Representa a peça editorial principal enviada pelo portal interno."""

    class Prioridade(models.TextChoices):
        BAIXA = "BAIXA", "Baixa"
        NORMAL = "NORMAL", "Normal"
        ALTA = "ALTA", "Alta"
        CRITICA = "CRITICA", "Crítica"

    class StatusEnvio(models.TextChoices):
        RASCUNHO = "RASCUNHO", "Rascunho"
        AGENDADA = "AGENDADA", "Agendada"
        PUBLICADA = "PUBLICADA", "Publicada"
        CANCELADA = "CANCELADA", "Cancelada"

    class OrigemTipo(models.TextChoices):
        SISTEMA = "SISTEMA", "Sistema"

    assunto = models.CharField("Assunto", max_length=220)
    corpo = models.TextField("Corpo")
    prioridade = models.CharField(
        "Prioridade",
        max_length=20,
        choices=Prioridade.choices,
        default=Prioridade.NORMAL,
    )
    status_envio = models.CharField(
        "Status de envio",
        max_length=20,
        choices=StatusEnvio.choices,
        default=StatusEnvio.RASCUNHO,
    )
    origem_tipo = models.CharField(
        "Origem pública",
        max_length=20,
        choices=OrigemTipo.choices,
        default=OrigemTipo.SISTEMA,
    )
    origem_app = models.CharField("App de origem", max_length=120, blank=True)
    origem_model = models.CharField("Model de origem", max_length=120, blank=True)
    origem_pk = models.CharField("PK de origem", max_length=120, blank=True)
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mensagens_criadas",
        verbose_name="Criada por",
    )
    publicar_em = models.DateTimeField("Publicar em", null=True, blank=True)
    publicada_em = models.DateTimeField("Publicada em", null=True, blank=True)
    expira_em = models.DateTimeField("Expira em", null=True, blank=True)
    payload_email = models.JSONField("Payload futuro de e-mail", default=dict, blank=True)
    usuarios_alvo = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        through="MensagemUsuarioAlvo",
        related_name="mensagens_audiencia_direta",
        verbose_name="Usuários selecionados",
    )
    setores_alvo = models.ManyToManyField(
        SetorNode,
        blank=True,
        through="MensagemSetorAlvo",
        related_name="mensagens_audiencia_setor",
        verbose_name="Setores selecionados",
    )
    created_at = models.DateTimeField("Criada em", auto_now_add=True)
    updated_at = models.DateTimeField("Atualizada em", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Mensagem"
        verbose_name_plural = "Mensagens"
        indexes = [
            models.Index(fields=["status_envio", "publicar_em"]),
            models.Index(fields=["status_envio", "publicada_em"]),
            models.Index(fields=["expira_em"]),
        ]

    def __str__(self):
        return self.assunto

    @property
    def esta_expirada(self) -> bool:
        """Indica se a mensagem já saiu da fila ativa de pendências."""

        return bool(self.expira_em and self.expira_em <= timezone.now())

    @property
    def pode_editar(self) -> bool:
        """Restringe edição aos estados anteriores à entrega definitiva."""

        return self.status_envio in {self.StatusEnvio.RASCUNHO, self.StatusEnvio.AGENDADA}


class MensagemUsuarioAlvo(models.Model):
    """Preserva os usuários originalmente escolhidos pelo emissor."""

    mensagem = models.ForeignKey(Mensagem, on_delete=models.CASCADE, related_name="audiencia_usuarios")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mensagem_audiencias_usuario",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Usuário alvo da mensagem"
        verbose_name_plural = "Usuários alvo da mensagem"
        unique_together = [("mensagem", "usuario")]
        ordering = ["mensagem_id", "usuario__username", "id"]

    def __str__(self):
        return f"{self.mensagem} -> {self.usuario}"


class MensagemSetorAlvo(models.Model):
    """Preserva os setores originalmente escolhidos pelo emissor."""

    mensagem = models.ForeignKey(Mensagem, on_delete=models.CASCADE, related_name="audiencia_setores")
    setor = models.ForeignKey(SetorNode, on_delete=models.CASCADE, related_name="mensagem_audiencias_setor")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Setor alvo da mensagem"
        verbose_name_plural = "Setores alvo da mensagem"
        unique_together = [("mensagem", "setor")]
        ordering = ["mensagem_id", "setor__group__name", "id"]

    def __str__(self):
        return f"{self.mensagem} -> {self.setor}"


class MensagemDestino(models.Model):
    """Representa a entrega efetiva para um usuário após a publicação."""

    class StatusDestinatario(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CIENTE = "CIENTE", "Ciente"

    mensagem = models.ForeignKey(Mensagem, on_delete=models.CASCADE, related_name="destinos")
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mensagens_recebidas",
    )
    status_destinatario = models.CharField(
        "Status do destinatário",
        max_length=20,
        choices=StatusDestinatario.choices,
        default=StatusDestinatario.PENDENTE,
    )
    entregue_em = models.DateTimeField("Entregue em", null=True, blank=True)
    visualizada_em = models.DateTimeField("Primeira visualização", null=True, blank=True)
    ciente_em = models.DateTimeField("Ciência em", null=True, blank=True)
    assunto_snapshot = models.CharField("Assunto entregue", max_length=220)
    corpo_snapshot = models.TextField("Corpo entregue")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Destino da mensagem"
        verbose_name_plural = "Destinos da mensagem"
        unique_together = [("mensagem", "usuario")]
        ordering = ["entregue_em", "id"]
        indexes = [
            models.Index(fields=["usuario", "status_destinatario"]),
            models.Index(fields=["usuario", "visualizada_em"]),
            models.Index(fields=["usuario", "ciente_em"]),
            models.Index(fields=["usuario", "entregue_em"]),
        ]

    def __str__(self):
        return f"{self.usuario} - {self.mensagem}"

    @property
    def esta_expirada(self) -> bool:
        """Reaproveita a regra de expiração da mensagem principal."""

        return self.mensagem.esta_expirada


class MensagemEvento(models.Model):
    """Mantém rastreabilidade das operações relevantes do módulo."""

    class TipoAcao(models.TextChoices):
        CRIACAO = "CRIACAO", "Criação"
        EDICAO = "EDICAO", "Edição"
        AGENDAMENTO = "AGENDAMENTO", "Agendamento"
        PUBLICACAO = "PUBLICACAO", "Publicação"
        CANCELAMENTO = "CANCELAMENTO", "Cancelamento"
        VISUALIZACAO = "VISUALIZACAO", "Visualização"
        CIENCIA = "CIENCIA", "Ciência"

    mensagem = models.ForeignKey(
        Mensagem,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="eventos",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_mensageria",
    )
    tipo_acao = models.CharField("Tipo de ação", max_length=20, choices=TipoAcao.choices)
    payload = models.JSONField("Informações complementares", default=dict, blank=True)
    created_at = models.DateTimeField("Data/hora", auto_now_add=True)

    class Meta:
        verbose_name = "Evento da mensagem"
        verbose_name_plural = "Eventos da mensagem"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["tipo_acao", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_acao_display()} - {self.created_at:%d/%m/%Y %H:%M}"

