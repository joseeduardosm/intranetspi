from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from acls.mixins import ACLRequiredMixin
from setores.services import build_setor_tree


class OrganogramaAccessMixin(LoginRequiredMixin, ACLRequiredMixin):
    login_url = reverse_lazy('login')
    recurso_slug = 'organograma'


class SetorOrganogramaView(OrganogramaAccessMixin, TemplateView):
    template_name = 'organograma/main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['org_tree'] = build_setor_tree()
        return context
