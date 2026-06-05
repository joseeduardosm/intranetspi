from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .models import RegraAcesso
from .forms import RegraAcessoForm

class ACLAdminRequiredMixin(UserPassesTestMixin):
    """Garante que apenas administradores do sistema gerenciem permissões."""
    def test_func(self):
        return self.request.user.is_authenticated and (self.request.user.is_superuser or self.request.user.is_staff)


class ACLRuleListView(LoginRequiredMixin, ACLAdminRequiredMixin, ListView):
    model = RegraAcesso
    template_name = 'acls/list.html'
    context_object_name = 'regras'
    paginate_by = 20

    def get_queryset(self):
        return RegraAcesso.objects.select_related('recurso', 'usuario', 'grupo').all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Regras de Acesso (ACL)"
        return context


class ACLRuleCreateView(LoginRequiredMixin, ACLAdminRequiredMixin, CreateView):
    model = RegraAcesso
    form_class = RegraAcessoForm
    template_name = 'acls/form.html'
    success_url = reverse_lazy('acls:list')

    def form_valid(self, form):
        messages.success(self.request, "Nova regra de acesso cadastrada.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Nova Regra de Acesso"
        context['voltar_url'] = reverse_lazy('acls:list')
        return context


class ACLRuleUpdateView(LoginRequiredMixin, ACLAdminRequiredMixin, UpdateView):
    model = RegraAcesso
    form_class = RegraAcessoForm
    template_name = 'acls/form.html'
    success_url = reverse_lazy('acls:list')

    def form_valid(self, form):
        messages.success(self.request, "Regra de acesso atualizada.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Editar Regra de Acesso"
        context['voltar_url'] = reverse_lazy('acls:list')
        return context


class ACLRuleDeleteView(LoginRequiredMixin, ACLAdminRequiredMixin, DeleteView):
    model = RegraAcesso
    template_name = 'acls/confirm_delete.html'
    success_url = reverse_lazy('acls:list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Excluir Regra de Acesso"
        context['descricao'] = f'Deseja excluir a regra de acesso "{self.object}"?'
        context['voltar_url'] = reverse_lazy('acls:list')
        return context
