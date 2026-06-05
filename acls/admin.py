from django.contrib import admin
from .models import Recurso, RegraAcesso

@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "slug", "descricao")
    search_fields = ("nome", "slug", "descricao")
    prepopulated_fields = {"slug": ("nome",)}


@admin.register(RegraAcesso)
class RegraAcessoAdmin(admin.ModelAdmin):
    list_display = ("id", "recurso", "nivel", "usuario", "grupo", "criado_em")
    list_filter = ("nivel", "recurso", "grupo")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "grupo__name", "recurso__nome")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("recurso", "usuario", "grupo")
