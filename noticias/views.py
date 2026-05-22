from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import FileResponse, Http404
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from .forms import NoticiaForm
from .models import Noticia
from .services import noticias_publicadas


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class NoticiaPublicListView(ListView):
    template_name = 'noticias/public_list.html'
    context_object_name = 'noticias'

    def get_queryset(self):
        return noticias_publicadas()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        noticias = list(context['noticias'])
        grid_noticias = noticias[1:3]
        context['carousel_noticias'] = noticias[:4]
        context['grid_slots'] = [
            {'noticia': grid_noticias[idx] if idx < len(grid_noticias) else None}
            for idx in range(2)
        ]
        return context


class NoticiaArchiveView(ListView):
    template_name = 'noticias/archive.html'
    context_object_name = 'noticias'
    paginate_by = 20

    def get_queryset(self):
        return noticias_publicadas()


class NoticiaPublicDetailView(DetailView):
    template_name = 'noticias/public_detail.html'
    context_object_name = 'noticia'

    def get_queryset(self):
        return noticias_publicadas()


@method_decorator(xframe_options_sameorigin, name='dispatch')
class NoticiaPdfView(DetailView):
    def get_queryset(self):
        return noticias_publicadas().exclude(anexo_pdf='')

    def get(self, request, *args, **kwargs):
        noticia = self.get_object()
        if not noticia.anexo_pdf:
            raise Http404('PDF nao encontrado.')
        response = FileResponse(noticia.anexo_pdf.open('rb'), content_type='application/pdf')
        response['Content-Disposition'] = 'inline'
        return response


class NoticiaManageListView(SuperuserRequiredMixin, ListView):
    model = Noticia
    template_name = 'noticias/manage_list.html'
    context_object_name = 'noticias'

    def get_queryset(self):
        queryset = Noticia.objects.all().order_by('-fixada', '-data_publicacao', '-id')
        status = self.request.GET.get('status')
        if status in Noticia.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_atual'] = self.request.GET.get('status', '')
        context['status_opcoes'] = Noticia.Status.choices
        return context


class NoticiaCreateView(SuperuserRequiredMixin, CreateView):
    model = Noticia
    form_class = NoticiaForm
    template_name = 'noticias/form.html'

    def get_success_url(self):
        return reverse('noticias:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Noticia criada.')
        return super().form_valid(form)


class NoticiaUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Noticia
    form_class = NoticiaForm
    template_name = 'noticias/form.html'

    def get_success_url(self):
        return reverse('noticias:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Noticia atualizada.')
        return super().form_valid(form)


class NoticiaDuplicateView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        duplicate = Noticia.objects.create(
            imagem_destaque=noticia.imagem_destaque,
            anexo_pdf=noticia.anexo_pdf,
            titulo=f'Copia de {noticia.titulo}',
            texto_noticia=noticia.texto_noticia,
            status=Noticia.Status.RASCUNHO,
            data_publicacao=None,
            fixada=noticia.fixada,
        )
        messages.success(request, 'Noticia duplicada como rascunho.')
        return redirect('noticias:update', pk=duplicate.pk)


class NoticiaDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Noticia
    template_name = 'noticias/confirm_delete.html'
    success_url = reverse_lazy('noticias:manage_list')


class NoticiaPublicarView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        noticia.status = Noticia.Status.PUBLICADA
        if not noticia.data_publicacao:
            noticia.data_publicacao = timezone.now()
        noticia.full_clean()
        noticia.save(update_fields=['status', 'data_publicacao', 'atualizado_em'])
        messages.success(request, 'Noticia publicada.')
        return redirect('noticias:manage_list')


class NoticiaRascunharView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        noticia = get_object_or_404(Noticia, pk=pk)
        noticia.status = Noticia.Status.RASCUNHO
        noticia.save(update_fields=['status', 'atualizado_em'])
        messages.success(request, 'Noticia movida para rascunho.')
        return redirect('noticias:manage_list')
