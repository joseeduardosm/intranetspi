# Criado por José Eduardo Santana Martins em 04/06/2026
# Controla as telas do módulo de setores, incluindo listagem, CRUD administrativo
# e regras de acesso para a árvore organizacional.
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from .forms import SetorForm
from .models import SetorNode
from .services import build_setor_tree


from acls.mixins import ACLRequiredMixin


class SetoresAccessMixin(LoginRequiredMixin, ACLRequiredMixin):
    """Centraliza autenticação e permissão ACL exigidas pelas telas de setores."""

    login_url = reverse_lazy('login')
    recurso_slug = 'setores'



class SetoresAdminMixin(SetoresAccessMixin, UserPassesTestMixin):
    """Restringe operações de manutenção a superusuários autenticados."""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class SetoresHomeView(SetoresAccessMixin, TemplateView):
    template_name = 'setores/home.html'


class SetorListView(SetoresAccessMixin, ListView):
    """Lista setores com busca por grupo atual ou grupo pai."""

    model = SetorNode
    template_name = 'setores/list.html'
    context_object_name = 'setores'
    paginate_by = 20

    def get_queryset(self):
        # A busca consulta grupos relacionados sem quebrar a ordenação estável da listagem.
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
    """Cria setores e delega ao formulário a criação do grupo Django vinculado."""

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
    """Atualiza dados do setor e mantém o grupo Django sincronizado pelo formulário."""

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
    """Remove setores somente quando não há filhos nem usuários vinculados."""

    model = SetorNode
    template_name = 'setores/confirm_delete.html'
    success_url = reverse_lazy('setores:list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        # A exclusão preserva a consistência da árvore e evita deixar vínculos órfãos.
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
        # O grupo é a entidade base do setor; apagá-lo aciona a remoção do SetorNode.
        self.object.group.delete()
        return redirect(self.success_url)
