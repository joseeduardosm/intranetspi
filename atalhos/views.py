# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Controlar o CRUD administrativo dos atalhos exibidos no portal.

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import AtalhoForm
from .models import Atalho


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Restringe a gestão de atalhos aos superusuários autenticados."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class AtalhoListView(SuperuserRequiredMixin, ListView):
    """Lista atalhos na ordem em que serão exibidos na área pública."""

    model = Atalho
    template_name = 'atalhos/manage_list.html'
    context_object_name = 'atalhos'

    def get_queryset(self):
        # A ordenação explícita reforça a prioridade visual configurada no cadastro.
        return Atalho.objects.all().order_by('ordem', 'id')


class AtalhoCreateView(SuperuserRequiredMixin, CreateView):
    """Cria um novo atalho com mensagem de confirmação ao finalizar."""

    model = Atalho
    form_class = AtalhoForm
    template_name = 'atalhos/form.html'

    def get_success_url(self):
        return reverse('atalhos:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Atalho criado.')
        return super().form_valid(form)


class AtalhoUpdateView(SuperuserRequiredMixin, UpdateView):
    """Edita um atalho existente mantendo o mesmo formulário do cadastro."""

    model = Atalho
    form_class = AtalhoForm
    template_name = 'atalhos/form.html'

    def get_success_url(self):
        return reverse('atalhos:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Atalho atualizado.')
        return super().form_valid(form)


class AtalhoDeleteView(SuperuserRequiredMixin, DeleteView):
    """Remove um atalho após confirmação explícita do superusuário."""

    model = Atalho
    template_name = 'atalhos/confirm_delete.html'
    success_url = reverse_lazy('atalhos:manage_list')
