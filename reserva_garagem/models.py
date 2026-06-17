"""Modelos do módulo de reserva de vagas de garagem."""

from __future__ import annotations

import random
import uuid

from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models
from django.urls import reverse


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


class VagaGaragem(models.Model):
    """Representa a vaga física que pode ser reservada na garagem."""

    nome = models.CharField("Nome", max_length=160)
    localizacao = models.CharField("Localização", max_length=200, blank=True)
    cor = models.CharField("Cor do calendário", max_length=7, default=random_calendar_color)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        verbose_name = "Vaga de garagem"
        verbose_name_plural = "Vagas de garagem"

    def __str__(self) -> str:
        return self.nome_exibicao

    @property
    def nome_exibicao(self) -> str:
        """Combina nome e localização quando houver, útil em listas e filtros."""

        if self.localizacao:
            return f"{self.nome} - {self.localizacao}"
        return self.nome

    def save(self, *args, **kwargs):
        """Garante cor preenchida para renderização consistente da agenda."""

        if not self.cor:
            self.cor = random_calendar_color()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("reserva_garagem:vaga_list")


class ConfiguracaoReservaGaragem(models.Model):
    """Mantém a parametrização operacional do módulo em registro único."""

    grupo_fiscais = models.ForeignKey(
        Group,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="configuracoes_reserva_garagem",
        verbose_name="Grupo de fiscais",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuração da reserva de garagem"
        verbose_name_plural = "Configurações da reserva de garagem"

    def __str__(self) -> str:
        if self.grupo_fiscais_id:
            return f"Configuração - {self.grupo_fiscais.name}"
        return "Configuração sem grupo de fiscais"

    @classmethod
    def singleton(cls):
        """Obtém ou cria a configuração única do módulo."""

        config, _created = cls.objects.get_or_create(pk=1)
        return config


class ReservaGaragem(models.Model):
    """Representa uma ocorrência diária de reserva de vaga de garagem."""

    class Status(models.TextChoices):
        AGUARDANDO_APROVACAO = "AGUARDANDO_APROVACAO", "Aguardando aprovação"
        DEFERIDA = "DEFERIDA", "Deferida"
        INDEFERIDA = "INDEFERIDA", "Indeferida"
        CANCELADA = "CANCELADA", "Cancelada"

    vaga = models.ForeignKey(
        VagaGaragem,
        on_delete=models.CASCADE,
        related_name="reservas",
        verbose_name="Vaga",
    )
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitacoes_reserva_garagem",
        verbose_name="Solicitante",
    )
    status = models.CharField(
        "Status",
        max_length=30,
        choices=Status.choices,
        default=Status.AGUARDANDO_APROVACAO,
    )
    data = models.DateField("Data")
    responsavel = models.CharField("Responsável", max_length=180)
    marca_veiculo = models.CharField("Marca do veículo", max_length=120)
    modelo_veiculo = models.CharField("Modelo do veículo", max_length=120)
    cor_veiculo = models.CharField("Cor do veículo", max_length=80)
    placa_veiculo = models.CharField("Placa do veículo", max_length=10)
    observacoes = models.TextField("Observações", blank=True)
    fiscal_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="analises_reserva_garagem",
        verbose_name="Fiscal responsável",
    )
    justificativa_indeferimento = models.TextField("Justificativa do indeferimento", blank=True)
    serie_id = models.UUIDField("Identificador da série", null=True, blank=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name = "Reserva de vaga"
        verbose_name_plural = "Reservas de vagas"
        indexes = [
            models.Index(fields=["status", "data"]),
            models.Index(fields=["vaga", "data", "status"]),
            models.Index(fields=["placa_veiculo", "data"]),
            models.Index(fields=["solicitante", "data"]),
        ]

    def __str__(self) -> str:
        return f"Reserva #{self.pk} - {self.vaga.nome_exibicao} - {self.data:%d/%m/%Y}"

    @property
    def pode_editar_solicitante(self) -> bool:
        """Solicitante só altera a reserva antes da análise fiscal."""

        return self.status == self.Status.AGUARDANDO_APROVACAO

    @property
    def serie_descricao(self) -> str:
        """Resume a série recorrente para uso em detalhe e listagens."""

        if not self.serie_id:
            return "Reserva avulsa"
        return f"Série {str(self.serie_id)[:8]}"

    @property
    def pertence_a_serie(self) -> bool:
        """Indica se a reserva faz parte de uma série materializada."""

        return bool(self.serie_id)

    def get_absolute_url(self):
        return reverse("reserva_garagem:reserva_detail", kwargs={"pk": self.pk})


class ReservaGaragemEvento(models.Model):
    """Registra a trilha de auditoria do ciclo da reserva."""

    class Acao(models.TextChoices):
        CRIACAO = "CRIACAO", "Criação"
        EDICAO = "EDICAO", "Edição"
        CANCELAMENTO = "CANCELAMENTO", "Cancelamento"
        DEFERIMENTO = "DEFERIMENTO", "Deferimento"
        INDEFERIMENTO = "INDEFERIMENTO", "Indeferimento"

    reserva = models.ForeignKey(
        ReservaGaragem,
        on_delete=models.CASCADE,
        related_name="eventos",
        verbose_name="Reserva",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_reserva_garagem",
        verbose_name="Usuário responsável",
    )
    acao = models.CharField("Ação", max_length=20, choices=Acao.choices)
    payload = models.JSONField("Detalhes complementares", default=dict, blank=True)
    criado_em = models.DateTimeField("Data/hora", auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "Evento da reserva de garagem"
        verbose_name_plural = "Eventos da reserva de garagem"

    def __str__(self) -> str:
        return f"{self.get_acao_display()} - {self.reserva_id}"
