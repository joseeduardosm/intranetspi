# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Exibir a árvore de setores do organograma respeitando login e ACL.

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from acls.mixins import ACLRequiredMixin
from setores.services import build_setor_tree


class OrganogramaAccessMixin(LoginRequiredMixin, ACLRequiredMixin):
    """Exige autenticação e permissão ACL para acessar o organograma."""

    login_url = reverse_lazy('login')
    recurso_slug = 'organograma'


class SetorOrganogramaView(OrganogramaAccessMixin, TemplateView):
    """Renderiza o organograma a partir da árvore hierárquica de setores."""

    template_name = 'organograma/main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # A árvore já vem estruturada pelo serviço do app setores para uso recursivo no template.
        context['org_tree'] = build_setor_tree()
        return context
