"""Administração do módulo de reserva de espaços."""

from django.contrib import admin

from .models import ObjetoReservavel, ReservaRecurso


@admin.register(ObjetoReservavel)
class ObjetoReservavelAdmin(admin.ModelAdmin):
    """Exibe objetos filtráveis por nome e localização."""

    list_display = ("nome", "localizacao", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "localizacao")


@admin.register(ReservaRecurso)
class ReservaRecursoAdmin(admin.ModelAdmin):
    """Facilita auditoria das reservas pelo Django Admin."""

    list_display = ("titulo", "objeto", "data", "hora_inicio", "hora_fim", "criado_por")
    list_filter = ("objeto", "data")
    search_fields = ("titulo", "responsavel", "objeto__nome")
