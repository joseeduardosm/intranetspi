from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import AtalhoForm
from .models import Atalho


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class AtalhoListView(SuperuserRequiredMixin, ListView):
    model = Atalho
    template_name = 'atalhos/manage_list.html'
    context_object_name = 'atalhos'

    def get_queryset(self):
        return Atalho.objects.all().order_by('ordem', 'id')


class AtalhoCreateView(SuperuserRequiredMixin, CreateView):
    model = Atalho
    form_class = AtalhoForm
    template_name = 'atalhos/form.html'

    def get_success_url(self):
        return reverse('atalhos:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Atalho criado.')
        return super().form_valid(form)


class AtalhoUpdateView(SuperuserRequiredMixin, UpdateView):
    model = Atalho
    form_class = AtalhoForm
    template_name = 'atalhos/form.html'

    def get_success_url(self):
        return reverse('atalhos:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Atalho atualizado.')
        return super().form_valid(form)


class AtalhoDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Atalho
    template_name = 'atalhos/confirm_delete.html'
    success_url = reverse_lazy('atalhos:manage_list')

