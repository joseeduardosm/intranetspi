"""Administração do módulo de reserva de espaços."""

from django.contrib import admin

from .models import ConfiguracaoReservaEspacos, ObjetoReservavel, ReservaRecurso, ReservaRecursoEvento


@admin.register(ObjetoReservavel)
class ObjetoReservavelAdmin(admin.ModelAdmin):
    """Exibe objetos filtráveis por nome e localização."""

    list_display = ("nome", "localizacao", "ativo")
    list_filter = ("ativo",)
    search_fields = ("nome", "localizacao")


@admin.register(ReservaRecurso)
class ReservaRecursoAdmin(admin.ModelAdmin):
    """Facilita auditoria das reservas pelo Django Admin."""

    list_display = ("titulo", "objeto", "data", "hora_inicio", "hora_fim", "status", "criado_por", "fiscal_responsavel")
    list_filter = ("objeto", "data", "status")
    search_fields = ("titulo", "responsavel", "objeto__nome")


@admin.register(ConfiguracaoReservaEspacos)
class ConfiguracaoReservaEspacosAdmin(admin.ModelAdmin):
    """Expõe a configuração singleton do grupo fiscal no admin."""

    list_display = ("id", "grupo_fiscais", "atualizado_em")


@admin.register(ReservaRecursoEvento)
class ReservaRecursoEventoAdmin(admin.ModelAdmin):
    """Facilita a leitura da trilha de auditoria pelo admin."""

    list_display = ("reserva", "acao", "usuario", "criado_em")
    list_filter = ("acao", "criado_em")
    search_fields = ("reserva__titulo", "usuario__username")
