# Criado por OpenAI Codex em 12/06/2026
# Modela frota, motoristas, solicitações de viagem e trilha de auditoria do módulo.

from __future__ import annotations

import random
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.urls import reverse
from django.utils import timezone


CALENDAR_COLORS = [
    "#1f4b99",
    "#0b6e4f",
    "#a64b00",
    "#7f1d5a",
    "#005f73",
    "#6c3f13",
    "#1d3557",
    "#c2410c",
    "#2f6aa8",
    "#8b1e3f",
]


def random_calendar_color() -> str:
    """Retorna uma cor da paleta usada nos eventos do calendário."""

    return random.choice(CALENDAR_COLORS)


class Carro(models.Model):
    """Representa um veículo disponível para viagens oficiais."""

    marca = models.CharField("Marca", max_length=120)
    modelo = models.CharField("Modelo", max_length=120)
    placa = models.CharField("Placa", max_length=10, unique=True)
    cor = models.CharField("Cor do calendário", max_length=7, default=random_calendar_color)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["marca", "modelo", "placa"]
        verbose_name = "Carro"
        verbose_name_plural = "Carros"

    def __str__(self) -> str:
        return self.nome_exibicao

    @property
    def nome_exibicao(self) -> str:
        """Monta um rótulo amigável para listas, filtros e calendários."""

        return f"{self.marca} {self.modelo} - {self.placa}"

    def save(self, *args, **kwargs):
        """Garante cor preenchida para renderização consistente."""

        if not self.cor:
            self.cor = random_calendar_color()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("reserva_carros:carro_list")


class Motorista(models.Model):
    """Cadastro próprio de motoristas utilizado na etapa de deferimento."""

    nome_completo = models.CharField("Nome completo", max_length=220)
    contato = models.CharField("Contato", max_length=120, blank=True)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome_completo", "id"]
        verbose_name = "Motorista"
        verbose_name_plural = "Motoristas"

    def __str__(self) -> str:
        return self.nome_completo

    def get_absolute_url(self):
        return reverse("reserva_carros:motorista_list")


class ConfiguracaoReservaCarros(models.Model):
    """Mantém a parametrização operacional do módulo em registro único."""

    grupo_fiscais = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="configuracoes_reserva_carros",
        verbose_name="Grupo de fiscais",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração da reserva de carros"
        verbose_name_plural = "Configurações da reserva de carros"

    def __str__(self) -> str:
        if self.grupo_fiscais_id:
            return f"Configuração - {self.grupo_fiscais.name}"
        return "Configuração sem grupo de fiscais"

    @classmethod
    def singleton(cls):
        """Obtém ou cria a configuração única do módulo."""

        config, _created = cls.objects.get_or_create(pk=1)
        return config


class ReservaCarro(models.Model):
    """Representa a solicitação e eventual operação de uma viagem oficial."""

    class Status(models.TextChoices):
        AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO", "Aguardando aprovação"
        DEFERIDA = "DEFERIDA", "Deferida"
        INDEFERIDA = "INDEFERIDA", "Indeferida"
        CANCELADA = "CANCELADA", "Cancelada"

    class ModoDestino(models.TextChoices):
        AGUARDAR_NO_LOCAL = "AGUARDAR_NO_LOCAL", "Aguardar no local"
        SOMENTE_DESEMBARQUE = "SOMENTE_DESEMBARQUE", "Somente desembarque"

    local_saida_padrao = "Secretaria de Parcerias em Investimentos"

    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitacoes_reserva_carro",
        verbose_name="Solicitante",
    )
    status = models.CharField(
        "Status",
        max_length=30,
        choices=Status.choices,
        default=Status.AGUARDANDO_APROVACAO,
    )
    saida_planejada_em = models.DateTimeField("Saída planejada")
    retorno_planejado_em = models.DateTimeField("Retorno planejado")
    local_saida = models.CharField("Local de saída", max_length=220, default=local_saida_padrao)
    destino_endereco = models.CharField("Destino", max_length=300)
    modo_destino = models.CharField(
        "Permanência no destino",
        max_length=30,
        choices=ModoDestino.choices,
    )
    motivo_viagem = models.TextField("Motivo da viagem")
    observacoes_solicitante = models.TextField("Observações do solicitante", blank=True)
    fiscal_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analises_reserva_carro",
        verbose_name="Fiscal responsável",
    )
    justificativa_indeferimento = models.TextField("Justificativa do indeferimento", blank=True)
    deslocamento_ida_minutos = models.PositiveIntegerField("Deslocamento de ida (min)", null=True, blank=True)
    deslocamento_retorno_minutos = models.PositiveIntegerField("Deslocamento de retorno (min)", null=True, blank=True)
    carro = models.ForeignKey(
        Carro,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservas",
        verbose_name="Carro",
    )
    motorista = models.ForeignKey(
        Motorista,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservas",
        verbose_name="Motorista",
    )
    inicio_bloqueio_em = models.DateTimeField("Início do bloqueio", null=True, blank=True)
    fim_bloqueio_em = models.DateTimeField("Fim do bloqueio", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-saida_planejada_em", "-id"]
        verbose_name = "Reserva de carro"
        verbose_name_plural = "Reservas de carros"
        indexes = [
            models.Index(fields=["status", "saida_planejada_em"]),
            models.Index(fields=["carro", "inicio_bloqueio_em", "fim_bloqueio_em"]),
            models.Index(fields=["motorista", "inicio_bloqueio_em", "fim_bloqueio_em"]),
        ]

    def __str__(self) -> str:
        return f"Viagem #{self.pk} - {self.solicitante}"

    @property
    def pode_editar_solicitante(self) -> bool:
        """Solicitante só altera a reserva antes da análise do fiscal."""

        return self.status == self.Status.AGUARDANDO_APROVACAO

    @property
    def janela_operacional_display(self) -> str:
        """Resume a janela real que bloqueia o carro e o motorista."""

        if not self.inicio_bloqueio_em or not self.fim_bloqueio_em:
            return "-"
        return (
            f"{timezone.localtime(self.inicio_bloqueio_em).strftime('%d/%m/%Y %H:%M')} até "
            f"{timezone.localtime(self.fim_bloqueio_em).strftime('%d/%m/%Y %H:%M')}"
        )

    @property
    def saida_local_display(self) -> str:
        """Garante exibição consistente do local institucional de saída."""

        return self.local_saida or self.local_saida_padrao

    def calcular_inicio_bloqueio(self):
        """Aplica a dilatação operacional anterior à saída planejada."""

        if self.deslocamento_ida_minutos is None:
            return None
        return self.saida_planejada_em - timedelta(minutes=self.deslocamento_ida_minutos)

    def calcular_fim_bloqueio(self):
        """Aplica a dilatação operacional posterior ao retorno planejado."""

        if self.deslocamento_retorno_minutos is None:
            return None
        return self.retorno_planejado_em + timedelta(minutes=self.deslocamento_retorno_minutos)

    def get_absolute_url(self):
        return reverse("reserva_carros:solicitacao_detail", kwargs={"pk": self.pk})


class ReservaCarroPassageiro(models.Model):
    """Relaciona os usuários que participarão da viagem solicitada."""

    reserva = models.ForeignKey(
        ReservaCarro,
        on_delete=models.CASCADE,
        related_name="passageiros_vinculos",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="viagens_como_passageiro",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["usuario__username", "id"]
        verbose_name = "Passageiro da reserva"
        verbose_name_plural = "Passageiros da reserva"
        unique_together = [("reserva", "usuario")]

    def __str__(self) -> str:
        return f"{self.reserva_id} - {self.usuario}"


class ReservaCarroEvento(models.Model):
    """Registra a trilha de auditoria do ciclo da reserva."""

    class Acao(models.TextChoices):
        CRIACAO = "CRIACAO", "Criação"
        EDICAO = "EDICAO", "Edição"
        CANCELAMENTO = "CANCELAMENTO", "Cancelamento"
        DEFERIMENTO = "DEFERIMENTO", "Deferimento"
        INDEFERIMENTO = "INDEFERIMENTO", "Indeferimento"

    reserva = models.ForeignKey(
        ReservaCarro,
        on_delete=models.CASCADE,
        related_name="eventos",
        verbose_name="Reserva",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_reserva_carro",
        verbose_name="Usuário responsável",
    )
    acao = models.CharField("Ação", max_length=20, choices=Acao.choices)
    payload = models.JSONField("Detalhes complementares", default=dict, blank=True)
    criado_em = models.DateTimeField("Data/hora", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "Evento da reserva de carro"
        verbose_name_plural = "Eventos da reserva de carro"

    def __str__(self) -> str:
        return f"{self.get_acao_display()} - {self.reserva_id}"

