"""Admin do módulo de reserva de garagem."""

from django.contrib import admin

from .models import ConfiguracaoReservaGaragem, ReservaGaragem, ReservaGaragemEvento, VagaGaragem


@admin.register(VagaGaragem)
class VagaGaragemAdmin(admin.ModelAdmin):
    list_display = ("nome", "localizacao", "ativo")
    search_fields = ("nome", "localizacao")


@admin.register(ReservaGaragem)
class ReservaGaragemAdmin(admin.ModelAdmin):
    list_display = ("vaga", "data", "placa_veiculo", "solicitante", "status")
    list_filter = ("status", "data", "vaga")
    search_fields = ("placa_veiculo", "marca_veiculo", "modelo_veiculo", "responsavel", "solicitante__username")


admin.site.register(ConfiguracaoReservaGaragem)
admin.site.register(ReservaGaragemEvento)
