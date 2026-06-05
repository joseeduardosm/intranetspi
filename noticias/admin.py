# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Registrar notícias no admin do Django com filtros editoriais.

from django.contrib import admin

from .models import Noticia


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    """Configura a listagem administrativa das notícias."""

    list_display = ('id', 'titulo', 'status', 'fixada', 'data_publicacao', 'atualizado_em')
    list_filter = ('status', 'fixada')
    search_fields = ('titulo', 'texto_noticia')
    ordering = ('-fixada', '-data_publicacao', '-id')
