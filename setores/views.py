from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import SetorForm
from .models import SetorNode
from .services import build_setor_tree


class SetoresAccessMixin(LoginRequiredMixin):
    login_url = reverse_lazy('login')


class SetoresAdminMixin(SetoresAccessMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class SetoresHomeView(SetoresAccessMixin, TemplateView):
    template_name = 'setores/home.html'


class SetorListView(SetoresAccessMixin, ListView):
    model = SetorNode
    template_name = 'setores/list.html'
    context_object_name = 'setores'
    paginate_by = 20

    def get_queryset(self):
        queryset = SetorNode.objects.select_related('group', 'parent__group').order_by('id')
        term = self.request.GET.get('q', '').strip()
        if term:
            queryset = queryset.filter(
                Q(group__name__icontains=term)
                | Q(parent__group__name__icontains=term)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '').strip()
        return context


class SetorCreateView(SetoresAdminMixin, CreateView):
    model = SetorNode
    form_class = SetorForm
    template_name = 'setores/form.html'

    def get_success_url(self):
        messages.success(self.request, 'Setor criado.')
        return reverse('setores:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo setor'
        context['voltar_url'] = reverse('setores:list')
        return context


class SetorUpdateView(SetoresAdminMixin, UpdateView):
    model = SetorNode
    form_class = SetorForm
    template_name = 'setores/form.html'

    def get_success_url(self):
        messages.success(self.request, 'Setor atualizado.')
        return reverse('setores:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar setor'
        context['voltar_url'] = reverse('setores:list')
        return context


class SetorDeleteView(SetoresAdminMixin, DeleteView):
    model = SetorNode
    template_name = 'setores/confirm_delete.html'
    success_url = reverse_lazy('setores:list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.children.exists() or self.object.memberships.exists():
            messages.error(
                request,
                'Não é possível excluir um setor com filhos ou usuários vinculados.',
            )
            self.object = None
            from django.shortcuts import redirect
            return redirect('setores:list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Setor excluído.')
        self.object.group.delete()
        return redirect(self.success_url)


class SetorOrganogramaView(SetoresAccessMixin, TemplateView):
    template_name = 'setores/organograma.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['org_tree'] = build_setor_tree()
        return context
