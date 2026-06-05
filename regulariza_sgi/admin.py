# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Registrar imóveis, ciclos e marcos no admin com recursos relacionados inline.

from django.contrib import admin

from .models import CicloProcessual, Imovel, ImovelAnexo, ImovelProcessoSEI, MarcoProcessual


class ProcessoSEIInline(admin.TabularInline):
    """Permite editar processos SEI dentro do cadastro do imóvel."""

    model = ImovelProcessoSEI
    extra = 0


class AnexoInline(admin.TabularInline):
    """Permite editar anexos dentro do cadastro do imóvel."""

    model = ImovelAnexo
    extra = 0


class CicloInline(admin.TabularInline):
    """Mostra ciclos processuais vinculados ao imóvel no admin."""

    model = CicloProcessual
    extra = 0
    show_change_link = True


@admin.register(Imovel)
class ImovelAdmin(admin.ModelAdmin):
    """Configura a listagem administrativa dos imóveis."""

    list_display = ('id', 'inscricao_imobiliaria', 'municipio', 'uf', 'numero_sgi', 'possui_cadin')
    search_fields = ('inscricao_imobiliaria', 'matricula', 'numero_sgi', 'municipio')
    inlines = [ProcessoSEIInline, AnexoInline, CicloInline]


@admin.register(CicloProcessual)
class CicloProcessualAdmin(admin.ModelAdmin):
    """Configura a listagem administrativa dos ciclos processuais."""

    list_display = ('id', 'imovel', 'numero', 'tipo', 'resultado', 'data_inicio', 'data_protocolo')
    list_filter = ('tipo', 'resultado')
    search_fields = ('imovel__inscricao_imobiliaria', 'numero_protocolo')


@admin.register(MarcoProcessual)
class MarcoProcessualAdmin(admin.ModelAdmin):
    """Configura a listagem administrativa dos marcos processuais."""

    list_display = ('id', 'ciclo', 'titulo', 'ordem', 'data_real', 'data_prevista')
    list_filter = ('tipo',)
