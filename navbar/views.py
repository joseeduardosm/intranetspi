# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Controlar o CRUD administrativo e a reordenação dos itens da navbar.

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import NavbarItemForm
from .models import NavbarItem
from .services import move_navbar_item, navbar_move_state, normalize_navbar_branch


class SuperuserRequiredMixin(UserPassesTestMixin):
    """Restringe a gestão da navbar aos superusuários autenticados."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class NavbarItemListView(SuperuserRequiredMixin, ListView):
    """Lista itens da navbar com filtros e estado de movimentação."""

    model = NavbarItem
    template_name = 'navbar/manage_list.html'
    context_object_name = 'items'

    def get_queryset(self):
        # Filtros opcionais ajudam a gerenciar menus ativos, inativos, raiz e submenus.
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
        # Calcula botões de subir/descer sem repetir consultas por linha no template.
        context['ativo_atual'] = self.request.GET.get('ativo', '')
        context['parent_atual'] = self.request.GET.get('parent', '')
        context['parents'] = NavbarItem.objects.filter(parent__isnull=True).order_by('ordem', 'titulo')
        move_state = navbar_move_state(context['items'])
        for item in context['items']:
            item.can_move_up = move_state.get(item.id, {}).get('up', False)
            item.can_move_down = move_state.get(item.id, {}).get('down', False)
        return context


class NavbarItemCreateView(SuperuserRequiredMixin, CreateView):
    """Cria um novo item de navbar e normaliza a ordem da ramificação."""

    model = NavbarItem
    form_class = NavbarItemForm
    template_name = 'navbar/form.html'

    def get_success_url(self):
        return reverse('navbar:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Item da navbar criado.')
        response = super().form_valid(form)
        normalize_navbar_branch(self.object.parent_id)
        return response


class NavbarItemUpdateView(SuperuserRequiredMixin, UpdateView):
    """Atualiza um item e normaliza a ordem do pai antigo e do novo pai."""

    model = NavbarItem
    form_class = NavbarItemForm
    template_name = 'navbar/form.html'

    def get_success_url(self):
        return reverse('navbar:manage_list')

    def form_valid(self, form):
        messages.success(self.request, 'Item da navbar atualizado.')
        parent_id_anterior = self.get_object().parent_id
        response = super().form_valid(form)
        normalize_navbar_branch(parent_id_anterior)
        normalize_navbar_branch(self.object.parent_id)
        return response


class NavbarItemDeleteView(SuperuserRequiredMixin, DeleteView):
    """Remove um item e renumera os irmãos restantes."""

    model = NavbarItem
    template_name = 'navbar/confirm_delete.html'
    success_url = reverse_lazy('navbar:manage_list')

    def form_valid(self, form):
        self.object = self.get_object()
        parent_id = self.object.parent_id
        response = super().form_valid(form)
        normalize_navbar_branch(parent_id)
        return response


class NavbarItemMoveView(SuperuserRequiredMixin, View):
    """Processa a movimentação de itens na listagem administrativa."""

    def post(self, request, pk):
        item = get_object_or_404(NavbarItem, pk=pk)
        direction = request.POST.get('direction')
        if direction in {'up', 'down'}:
            moved = move_navbar_item(item, direction)
            if moved:
                messages.success(request, 'Ordem da navbar atualizada.')
            else:
                messages.info(request, 'Esse item já está no limite da ordem.')

        next_url = request.POST.get('next') or reverse('navbar:manage_list')
        return HttpResponseRedirect(next_url)
