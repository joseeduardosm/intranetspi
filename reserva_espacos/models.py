"""Modelos do módulo de reserva de espaços sem segmentação por categoria."""

from __future__ import annotations

import random
import uuid
from datetime import datetime

from django.conf import settings
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
    """Retorna uma cor estável da paleta usada nos marcadores do calendário."""

    return random.choice(CALENDAR_COLORS)


class ObjetoReservavel(models.Model):
    """Representa o recurso concreto que pode receber reservas."""

    nome = models.CharField("Nome", max_length=160)
    localizacao = models.CharField("Localização", max_length=200, blank=True)
    cor = models.CharField("Cor do calendário", max_length=7, default=random_calendar_color)
    ativo = models.BooleanField("Ativo", default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        verbose_name = "Objeto reservável"
        verbose_name_plural = "Objetos reserváveis"

    def __str__(self) -> str:
        return self.nome

    @property
    def nome_exibicao(self) -> str:
        """Combina nome e localização quando houver, útil nas listas e filtros."""

        if self.localizacao:
            return f"{self.nome} - {self.localizacao}"
        return self.nome

    def save(self, *args, **kwargs):
        """Garante cor preenchida para não quebrar os marcadores do calendário."""

        if not self.cor:
            self.cor = random_calendar_color()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Retorna a rota padrão da listagem de objetos do módulo."""

        return reverse("reserva_espacos:objeto_list")


class ReservaRecurso(models.Model):
    """Registro transacional de reserva para um objeto específico."""

    objeto = models.ForeignKey(
        ObjetoReservavel,
        on_delete=models.CASCADE,
        related_name="reservas",
        verbose_name="Objeto",
    )
    data = models.DateField("Data")
    hora_inicio = models.TimeField("Hora de início")
    hora_fim = models.TimeField("Hora de fim")
    titulo = models.CharField("Título da reserva", max_length=180)
    responsavel = models.CharField("Responsável", max_length=180)
    observacoes = models.TextField("Observações", blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reserva_espacos_criadas",
        verbose_name="Criado por",
    )
    serie_id = models.UUIDField("Identificador da série", null=True, blank=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data", "hora_inicio", "id"]
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"

    def __str__(self) -> str:
        return f"{self.titulo} - {self.objeto.nome}"

    @property
    def inicio_datetime(self) -> datetime:
        """Combina data e hora inicial para comparações temporais."""

        return datetime.combine(self.data, self.hora_inicio)

    @property
    def fim_datetime(self) -> datetime:
        """Combina data e hora final para comparações temporais."""

        return datetime.combine(self.data, self.hora_fim)

    def pertence_a_serie(self) -> bool:
        """Indica se a reserva faz parte de uma série recorrente."""

        return bool(self.serie_id)

    def gerar_serie_id(self) -> uuid.UUID:
        """Cria e guarda um identificador de série quando ele ainda não existe."""

        if not self.serie_id:
            self.serie_id = uuid.uuid4()
        return self.serie_id

    def get_absolute_url(self):
        """Retorna a rota canônica do detalhe da reserva."""

        return reverse("reserva_espacos:reserva_detail", kwargs={"pk": self.pk})
