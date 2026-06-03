from django.contrib import admin

from .models import CicloProcessual, Imovel, ImovelAnexo, ImovelProcessoSEI, MarcoProcessual


class ProcessoSEIInline(admin.TabularInline):
    model = ImovelProcessoSEI
    extra = 0


class AnexoInline(admin.TabularInline):
    model = ImovelAnexo
    extra = 0


class CicloInline(admin.TabularInline):
    model = CicloProcessual
    extra = 0
    show_change_link = True


@admin.register(Imovel)
class ImovelAdmin(admin.ModelAdmin):
    list_display = ('id', 'inscricao_imobiliaria', 'municipio', 'uf', 'numero_sgi', 'possui_cadin')
    search_fields = ('inscricao_imobiliaria', 'matricula', 'numero_sgi', 'municipio')
    inlines = [ProcessoSEIInline, AnexoInline, CicloInline]


@admin.register(CicloProcessual)
class CicloProcessualAdmin(admin.ModelAdmin):
    list_display = ('id', 'imovel', 'numero', 'tipo', 'resultado', 'data_inicio', 'data_protocolo')
    list_filter = ('tipo', 'resultado')
    search_fields = ('imovel__inscricao_imobiliaria', 'numero_protocolo')


@admin.register(MarcoProcessual)
class MarcoProcessualAdmin(admin.ModelAdmin):
    list_display = ('id', 'ciclo', 'titulo', 'ordem', 'data_real', 'data_prevista')
    list_filter = ('tipo',)

# Register your models here.
