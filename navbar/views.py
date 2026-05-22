from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import NavbarItemForm
from .models import NavbarItem


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class NavbarItemListView(SuperuserRequiredMixin, ListView):
    model = NavbarItem
    template_name = 'navbar/manage_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        queryset = NavbarItem.objects.select_related('parent').order_by('parent__ordem', 'parent__titulo', 'ordem', 'titulo')
        ativo = self.request.GET.get('ativo')
        parent = self.request.GET.get('parent')
        if ativo in {'1', '0'}:
            queryset = queryset.filter(ativo=(ativo == '1'))
        if parent == 'raiz':
            queryset = queryset.filter(parent__isnull=True)
        elif parent:
            queryset = queryset.filter(parent_id=parent)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['ativo_atual'] = self.request.GET.get('ativo', '')
        context['parent_atual'] = self.request.GET.get('parent', '')
        context['parents'] = NavbarItem.objects.filter(parent__isnull=True).order_by('ordem', 'titulo')
        return context


class NavbarItemCreateView(SuperuserRequiredMixin, CreateView):
    model = NavbarItem
    form_class = NavbarItemForm
    template_name = 'navbar/form.html'

    def get_success_url(self):
        return reverse('navbar:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Item da navbar criado.')
        return super().form_valid(form)


class NavbarItemUpdateView(SuperuserRequiredMixin, UpdateView):
    model = NavbarItem
    form_class = NavbarItemForm
    template_name = 'navbar/form.html'

    def get_success_url(self):
        return reverse('navbar:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Item da navbar atualizado.')
        return super().form_valid(form)


class NavbarItemDeleteView(SuperuserRequiredMixin, DeleteView):
    model = NavbarItem
    template_name = 'navbar/confirm_delete.html'
    success_url = reverse_lazy('navbar:manage_list')
