from django.contrib import admin

from .models import Noticia


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ('id', 'titulo', 'status', 'fixada', 'data_publicacao', 'atualizado_em')
    list_filter = ('status', 'fixada')
    search_fields = ('titulo', 'texto_noticia')
    ordering = ('-fixada', '-data_publicacao', '-id')
