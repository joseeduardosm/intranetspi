# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Entregar o CRUD e o fluxo operacional do Contratos V2 com checklist, competências, avaliação e pagamento.

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Max, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, UpdateView, View

from acls.mixins import ACLRequiredMixin

from .forms import (
    AvaliacaoCompetenciaV2Form,
    ChecklistModeloItemV2Form,
    ChecklistModeloV2Form,
    CompetenciaChecklistUploadForm,
    CompetenciaMedicaoLoteV2Form,
    CompetenciaPagamentoExecucaoV2Form,
    ContratoItemV2Form,
    ContratoV2Form,
    EscalaNotaAvaliacaoV2Form,
    FaixaLiberacaoAvaliacaoV2Form,
    FormularioAvaliacaoV2Form,
    GrupoAvaliacaoV2Form,
    ItemAvaliacaoV2Form,
)
from .models import (
    AvaliacaoQualidadeCompetenciaV2,
    ChecklistCompetenciaAnexoV2,
    ChecklistModeloItemV2,
    ChecklistModeloV2,
    CompetenciaPagamentoV2,
    ContratoItemV2,
    ContratoV2,
    EscalaNotaAvaliacaoV2,
    FaixaLiberacaoAvaliacaoV2,
    FormularioAvaliacaoV2,
    GrupoAvaliacaoV2,
    ItemAvaliacaoV2,
    MedicaoItemCompetenciaV2,
)
from .services import (
    avaliacao_v2_esta_concluida,
    criar_avaliacao_shell_competencia_v2,
    recalcular_avaliacao_v2,
    recalcular_competencia_v2,
    usuario_pode_gerir_contrato_v2,
)


class ContratosV2AccessMixin(LoginRequiredMixin, ACLRequiredMixin):
    """Protege o módulo por login e ACL própria da versão nova."""

    recurso_slug = 'contratos_v2'


class ContratosV2WriteMixin(ContratosV2AccessMixin):
    """Exige escrita nas operações de criação, edição e exclusão."""

    acl_nivel_minimo = 'MODIFICACAO'


def assign_owner(instance, request):
    """Mantém autoria e atualização alinhadas às operações do CRUD."""

    if hasattr(instance, 'criado_por_id') and not instance.criado_por_id:
        instance.criado_por = request.user
    if hasattr(instance, 'atualizado_por_id'):
        instance.atualizado_por = request.user
    return instance


def serializar_responsavel_v2(label, usuario):
    """Entrega os dados do responsável no formato esperado pelo modal de ramais."""

    perfil = getattr(usuario, 'perfil', None)
    foto = getattr(perfil, 'foto', None)
    foto_url = ''
    if foto and getattr(foto, 'name', ''):
        try:
            foto_url = foto.url
        except ValueError:
            foto_url = ''

    nome = getattr(perfil, 'nome_completo', None) or usuario.get_full_name() or usuario.username
    return {
        'label': label,
        'nome': nome,
        'iniciais': ''.join(parte[0].upper() for parte in nome.split()[:2] if parte) or nome[:1].upper(),
        'cargo': getattr(perfil, 'cargo', '') or '-',
        'setor': getattr(perfil, 'setor', '') or '-',
        'email': usuario.email or '-',
        'ramal': getattr(perfil, 'ramal', '') or '-',
        'celular': getattr(perfil, 'celular', '') or '',
        'whatsapp': perfil.whatsapp_url if perfil else '',
        'local': perfil.andar_bloco_display if perfil else '-',
        'foto_url': foto_url,
    }


def redirect_contract_detail(contrato):
    return redirect('contratos_v2:contrato_detail', pk=contrato.pk)


class ContractManagePermissionMixin:
    """Garante que apenas gestor/admin operem cadastros estruturantes do contrato."""

    contrato = None

    def ensure_manage_permission(self, request, contrato):
        if usuario_pode_gerir_contrato_v2(request.user, contrato):
            return None
        messages.error(request, 'Somente o gestor do contrato ou administradores do sistema podem executar esta ação.')
        return redirect_contract_detail(contrato)


class ContractOperatePermissionMixin:
    """Centraliza bloqueios operacionais por etapa da competência."""

    def deny(self, contrato, message):
        messages.error(self.request, message)
        return redirect_contract_detail(contrato)


class ContratoV2ListView(ContratosV2AccessMixin, ListView):
    model = ContratoV2
    template_name = 'contratos_v2/contrato_list.html'
    context_object_name = 'contratos'
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            ContratoV2.objects.select_related(
                'empresa_contratada',
                'fiscal_administrativo__perfil',
                'fiscal_tecnico__perfil',
                'gestor_contrato__perfil',
            )
        )
        term = self.request.GET.get('q', '').strip()
        if term:
            queryset = queryset.filter(
                Q(numero_contrato__icontains=term)
                | Q(apelido__icontains=term)
                | Q(objeto__icontains=term)
                | Q(empresa_contratada__razao_social__icontains=term)
                | Q(empresa_contratada__cnpj__icontains=term)
                | Q(fiscal_administrativo__username__icontains=term)
                | Q(fiscal_administrativo__perfil__nome_completo__icontains=term)
                | Q(fiscal_tecnico__username__icontains=term)
                | Q(fiscal_tecnico__perfil__nome_completo__icontains=term)
                | Q(gestor_contrato__username__icontains=term)
                | Q(gestor_contrato__perfil__nome_completo__icontains=term)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '').strip()
        return context


class ContratoV2CreateView(ContratosV2WriteMixin, CreateView):
    model = ContratoV2
    form_class = ContratoV2Form
    template_name = 'contratos_v2/contrato_form.html'

    def form_valid(self, form):
        assign_owner(form.instance, self.request)
        messages.success(self.request, 'Contrato V2 cadastrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo contrato'
        return context


class ContratoV2DetailView(ContratosV2AccessMixin, DetailView):
    model = ContratoV2
    template_name = 'contratos_v2/contrato_detail.html'
    context_object_name = 'contrato'

    def get_queryset(self):
        return ContratoV2.objects.select_related(
            'empresa_contratada',
            'fiscal_administrativo__perfil',
            'fiscal_tecnico__perfil',
            'gestor_contrato__perfil',
        ).prefetch_related(
            'itens',
            Prefetch('checklist_modelos', queryset=ChecklistModeloV2.objects.prefetch_related('itens')),
            Prefetch('formularios_avaliacao', queryset=FormularioAvaliacaoV2.objects.prefetch_related('escalas', 'faixas_liberacao', 'grupos__itens')),
            Prefetch(
                'competencias',
                queryset=CompetenciaPagamentoV2.objects.prefetch_related(
                    'checklist_itens__anexo',
                    'medicoes__item_contrato',
                    'avaliacao_qualidade__itens',
                ).order_by('periodo_inicio', 'id'),
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contrato = self.object
        context['responsaveis'] = [
            serializar_responsavel_v2('Fiscal administrativo', contrato.fiscal_administrativo),
            serializar_responsavel_v2('Fiscal técnico', contrato.fiscal_tecnico),
            serializar_responsavel_v2('Gestor contrato', contrato.gestor_contrato),
        ]
        context['usuario_pode_gerir'] = contrato.usuario_pode_gerir(self.request.user)
        context['usuario_pode_checklist'] = contrato.usuario_pode_preencher_checklist(self.request.user)
        context['usuario_pode_medicao'] = contrato.usuario_pode_preencher_medicao(self.request.user)
        context['usuario_pode_avaliacao'] = contrato.usuario_pode_preencher_avaliacao(self.request.user)
        return context


class ContratoV2UpdateView(ContratosV2WriteMixin, UpdateView):
    model = ContratoV2
    form_class = ContratoV2Form
    template_name = 'contratos_v2/contrato_form.html'

    def form_valid(self, form):
        assign_owner(form.instance, self.request)
        messages.success(self.request, 'Contrato V2 atualizado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar contrato'
        return context


class ContratoV2DeleteView(ContratosV2WriteMixin, DeleteView):
    model = ContratoV2
    template_name = 'contratos_v2/confirm_delete.html'
    success_url = reverse_lazy('contratos_v2:contrato_list')

    def form_valid(self, form):
        messages.success(self.request, 'Contrato V2 excluído com sucesso.')
        return super().form_valid(form)


class ContratoV2ChildCreateBase(ContratosV2WriteMixin):
    contrato = None

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(ContratoV2, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)


class ContratoItemV2CreateView(ContratoV2ChildCreateBase, CreateView):
    model = ContratoItemV2
    form_class = ContratoItemV2Form
    template_name = 'contratos_v2/contrato_item_form.html'

    def get_initial(self):
        initial = super().get_initial()
        initial['ordem'] = (self.contrato.itens.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        return initial

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        if not form.instance.ordem:
            form.instance.ordem = (self.contrato.itens.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        elif self.contrato.itens.filter(ordem=form.instance.ordem).exists():
            form.add_error('ordem', 'Já existe um item com essa numeração neste contrato.')
            return self.form_invalid(form)
        messages.success(self.request, 'Item do contrato cadastrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.contrato.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo item - {self.contrato.numero_contrato}'
        context['contrato'] = self.contrato
        return context


class ContratoItemV2UpdateView(ContratosV2WriteMixin, UpdateView):
    model = ContratoItemV2
    form_class = ContratoItemV2Form
    template_name = 'contratos_v2/contrato_item_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(ContratoV2, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ContratoItemV2.objects.filter(contrato=self.contrato)

    def form_valid(self, form):
        if not form.instance.ordem:
            form.instance.ordem = self.object.ordem
        conflito = self.contrato.itens.exclude(pk=self.object.pk).filter(ordem=form.instance.ordem).exists()
        if conflito:
            form.add_error('ordem', 'Já existe um item com essa numeração neste contrato.')
            return self.form_invalid(form)
        messages.success(self.request, 'Item do contrato atualizado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.contrato.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar item - {self.contrato.numero_contrato}'
        context['contrato'] = self.contrato
        return context


class ContratoItemV2DeleteView(ContratosV2WriteMixin, DeleteView):
    model = ContratoItemV2
    template_name = 'contratos_v2/contrato_item_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(ContratoV2, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ContratoItemV2.objects.filter(contrato=self.contrato)

    def get_success_url(self):
        messages.success(self.request, 'Item do contrato excluído com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.contrato.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['contrato'] = self.contrato
        return context


class ChecklistModeloV2CreateView(ContratoV2ChildCreateBase, ContractManagePermissionMixin, CreateView):
    model = ChecklistModeloV2
    form_class = ChecklistModeloV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        response = self.ensure_manage_permission(request, self.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Versão de checklist cadastrada com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.contrato.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova versão de checklist'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.contrato.pk])
        return context


class ChecklistModeloV2UpdateView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = ChecklistModeloV2
    form_class = ChecklistModeloV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar versão de checklist'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])
        return context


class ChecklistModeloV2DeleteView(ContratosV2WriteMixin, ContractManagePermissionMixin, DeleteView):
    model = ChecklistModeloV2
    template_name = 'contratos_v2/entity_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Versão de checklist excluída com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir versão de checklist'
        context['descricao_objeto'] = self.object.nome
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])
        return context


class ChecklistModeloItemV2CreateView(ContratosV2WriteMixin, ContractManagePermissionMixin, CreateView):
    model = ChecklistModeloItemV2
    form_class = ChecklistModeloItemV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.modelo = get_object_or_404(ChecklistModeloV2, pk=kwargs['modelo_pk'])
        response = self.ensure_manage_permission(request, self.modelo.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['ordem'] = (self.modelo.itens.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        return initial

    def form_valid(self, form):
        form.instance.modelo = self.modelo
        if not form.instance.ordem:
            form.instance.ordem = (self.modelo.itens.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        messages.success(self.request, 'Item do checklist cadastrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.modelo.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo item - {self.modelo.nome}'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.modelo.contrato_id])
        return context


class ChecklistModeloItemV2UpdateView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = ChecklistModeloItemV2
    form_class = ChecklistModeloItemV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.modelo.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.modelo.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar item do checklist'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.modelo.contrato_id])
        return context


class ChecklistModeloItemV2DeleteView(ContratosV2WriteMixin, ContractManagePermissionMixin, DeleteView):
    model = ChecklistModeloItemV2
    template_name = 'contratos_v2/entity_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.modelo.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Item do checklist excluído com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.object.modelo.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir item do checklist'
        context['descricao_objeto'] = self.object.titulo
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.modelo.contrato_id])
        return context


class FormularioAvaliacaoV2CreateView(ContratoV2ChildCreateBase, ContractManagePermissionMixin, CreateView):
    model = FormularioAvaliacaoV2
    form_class = FormularioAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        response = self.ensure_manage_permission(request, self.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = FormularioAvaliacaoV2(contrato=self.contrato)
        return kwargs

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        response = super().form_valid(form)
        messages.success(self.request, 'Formulário de avaliação cadastrado com sucesso.')
        return response

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.contrato.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo formulário de avaliação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.contrato.pk])
        return context


class FormularioAvaliacaoV2UpdateView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = FormularioAvaliacaoV2
    form_class = FormularioAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Formulário de avaliação atualizado com sucesso.')
        return response

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar formulário de avaliação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])
        return context


class FormularioAvaliacaoV2DeleteView(ContratosV2WriteMixin, ContractManagePermissionMixin, DeleteView):
    model = FormularioAvaliacaoV2
    template_name = 'contratos_v2/entity_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        try:
            return super().delete(request, *args, **kwargs)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect_contract_detail(self.object.contrato)

    def get_success_url(self):
        messages.success(self.request, 'Formulário de avaliação excluído com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir formulário de avaliação'
        context['descricao_objeto'] = self.object.nome
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])
        return context


class EscalaNotaAvaliacaoV2CreateView(ContratosV2WriteMixin, ContractManagePermissionMixin, CreateView):
    model = EscalaNotaAvaliacaoV2
    form_class = EscalaNotaAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.formulario = get_object_or_404(FormularioAvaliacaoV2, pk=kwargs['formulario_pk'])
        response = self.ensure_manage_permission(request, self.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.formulario = self.formulario
        form.instance.ordem = (self.formulario.escalas.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        messages.success(self.request, 'Nota da escala cadastrada com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova nota da escala'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.formulario.contrato_id])
        return context


class EscalaNotaAvaliacaoV2UpdateView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = EscalaNotaAvaliacaoV2
    form_class = EscalaNotaAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar nota da escala'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])
        return context


class EscalaNotaAvaliacaoV2DeleteView(ContratosV2WriteMixin, ContractManagePermissionMixin, DeleteView):
    model = EscalaNotaAvaliacaoV2
    template_name = 'contratos_v2/entity_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Nota da escala excluída com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir nota da escala'
        context['descricao_objeto'] = str(self.object)
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])
        return context


class FaixaLiberacaoAvaliacaoV2CreateView(ContratosV2WriteMixin, ContractManagePermissionMixin, CreateView):
    model = FaixaLiberacaoAvaliacaoV2
    form_class = FaixaLiberacaoAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.formulario = get_object_or_404(FormularioAvaliacaoV2, pk=kwargs['formulario_pk'])
        response = self.ensure_manage_permission(request, self.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.formulario = self.formulario
        form.instance.ordem = (self.formulario.faixas_liberacao.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        messages.success(self.request, 'Faixa de liberação cadastrada com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova faixa de liberação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.formulario.contrato_id])
        return context


class FaixaLiberacaoAvaliacaoV2UpdateView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = FaixaLiberacaoAvaliacaoV2
    form_class = FaixaLiberacaoAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar faixa de liberação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])
        return context


class FaixaLiberacaoAvaliacaoV2DeleteView(ContratosV2WriteMixin, ContractManagePermissionMixin, DeleteView):
    model = FaixaLiberacaoAvaliacaoV2
    template_name = 'contratos_v2/entity_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Faixa de liberação excluída com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir faixa de liberação'
        context['descricao_objeto'] = str(self.object)
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])
        return context


class GrupoAvaliacaoV2CreateView(ContratosV2WriteMixin, ContractManagePermissionMixin, CreateView):
    model = GrupoAvaliacaoV2
    form_class = GrupoAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.formulario = get_object_or_404(FormularioAvaliacaoV2, pk=kwargs['formulario_pk'])
        response = self.ensure_manage_permission(request, self.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.formulario = self.formulario
        form.instance.ordem = (self.formulario.grupos.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        messages.success(self.request, 'Grupo de avaliação cadastrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo grupo de avaliação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.formulario.contrato_id])
        return context


class GrupoAvaliacaoV2UpdateView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = GrupoAvaliacaoV2
    form_class = GrupoAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar grupo de avaliação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])
        return context


class GrupoAvaliacaoV2DeleteView(ContratosV2WriteMixin, ContractManagePermissionMixin, DeleteView):
    model = GrupoAvaliacaoV2
    template_name = 'contratos_v2/entity_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Grupo de avaliação excluído com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir grupo de avaliação'
        context['descricao_objeto'] = self.object.nome
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.formulario.contrato_id])
        return context


class ItemAvaliacaoV2CreateView(ContratosV2WriteMixin, ContractManagePermissionMixin, CreateView):
    model = ItemAvaliacaoV2
    form_class = ItemAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.grupo = get_object_or_404(GrupoAvaliacaoV2, pk=kwargs['grupo_pk'])
        response = self.ensure_manage_permission(request, self.grupo.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.grupo = self.grupo
        # A ordem do item é sempre sequencial dentro do grupo para evitar divergência entre tela e banco.
        form.instance.ordem = (self.grupo.itens.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        messages.success(self.request, 'Item de avaliação cadastrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.grupo.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo item de avaliação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.grupo.formulario.contrato_id])
        return context


class ItemAvaliacaoV2UpdateView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = ItemAvaliacaoV2
    form_class = ItemAvaliacaoV2Form
    template_name = 'contratos_v2/entity_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.grupo.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.grupo.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar item de avaliação'
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.grupo.formulario.contrato_id])
        return context


class ItemAvaliacaoV2DeleteView(ContratosV2WriteMixin, ContractManagePermissionMixin, DeleteView):
    model = ItemAvaliacaoV2
    template_name = 'contratos_v2/entity_confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.grupo.formulario.contrato)
        if response:
            return response
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        messages.success(self.request, 'Item de avaliação excluído com sucesso.')
        return reverse('contratos_v2:contrato_detail', args=[self.object.grupo.formulario.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir item de avaliação'
        context['descricao_objeto'] = self.object.descricao[:120]
        context['cancel_url'] = reverse('contratos_v2:contrato_detail', args=[self.object.grupo.formulario.contrato_id])
        return context


class CompetenciasGenerateView(ContratosV2WriteMixin, ContractManagePermissionMixin, View):
    def post(self, request, *args, **kwargs):
        contrato = get_object_or_404(ContratoV2, pk=kwargs['contrato_pk'])
        response = self.ensure_manage_permission(request, contrato)
        if response:
            return response
        try:
            contrato.gerar_competencias()
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect_contract_detail(contrato)
        messages.success(request, 'Competências geradas com sucesso.')
        return redirect_contract_detail(contrato)


class CompetenciaChecklistUpdateView(ContratosV2WriteMixin, ContractOperatePermissionMixin, FormView):
    form_class = CompetenciaChecklistUploadForm
    template_name = 'contratos_v2/competencia_checklist_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.competencia = get_object_or_404(
            CompetenciaPagamentoV2.objects.select_related('contrato'),
            pk=kwargs['competencia_pk'],
        )
        if not self.competencia.contrato.usuario_pode_preencher_checklist(request.user):
            return self.deny(self.competencia.contrato, 'Você não pode preencher o checklist desta competência.')
        if self.competencia.status in {self.competencia.Status.PAGA, self.competencia.Status.CANCELADA}:
            return self.deny(self.competencia.contrato, 'A competência já foi encerrada.')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['competencia'] = self.competencia
        return kwargs

    def form_valid(self, form):
        for item in form.itens:
            novo_arquivo = form.cleaned_data.get(f'arquivo_{item.pk}')
            limpar = form.cleaned_data.get(f'limpar_{item.pk}')
            existente = item.anexo_principal
            if limpar and existente:
                existente.delete()
                continue
            if not novo_arquivo:
                continue
            if existente:
                existente.arquivo = novo_arquivo
                existente.nome_exibicao = ''
                existente.save(update_fields=['arquivo', 'nome_exibicao', 'atualizado_em'])
            else:
                ChecklistCompetenciaAnexoV2.objects.create(item=item, arquivo=novo_arquivo, nome_exibicao='')
        recalcular_competencia_v2(self.competencia)
        messages.success(self.request, 'Checklist atualizado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Checklist da competência'
        context['competencia'] = self.competencia
        context['contrato'] = self.competencia.contrato
        return context


class CompetenciaMedicaoUpdateView(ContratosV2WriteMixin, ContractOperatePermissionMixin, FormView):
    form_class = CompetenciaMedicaoLoteV2Form
    template_name = 'contratos_v2/competencia_medicao_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.competencia = get_object_or_404(
            CompetenciaPagamentoV2.objects.select_related('contrato'),
            pk=kwargs['competencia_pk'],
        )
        if not self.competencia.contrato.usuario_pode_preencher_medicao(request.user):
            return self.deny(self.competencia.contrato, 'Você não pode preencher a medição desta competência.')
        if self.competencia.checklist_itens.filter(obrigatorio=True, concluido=False).exists():
            return self.deny(self.competencia.contrato, 'Só é possível partir para a medição com o checklist preenchido.')
        if self.competencia.status in {self.competencia.Status.PAGA, self.competencia.Status.CANCELADA}:
            return self.deny(self.competencia.contrato, 'A competência já foi encerrada.')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['contrato'] = self.competencia.contrato
        kwargs['competencia'] = self.competencia
        return kwargs

    def form_valid(self, form):
        # O pró-rata fica salvo na competência para uso posterior no cálculo financeiro da etapa.
        self.competencia.aplicar_pro_rata = bool(form.cleaned_data.get('aplicar_pro_rata', False))
        for item in form.itens:
            quantidade = form.cleaned_data.get(f'quantidade_{item.pk}')
            if quantidade in (None, ''):
                continue
            if quantidade == 0:
                MedicaoItemCompetenciaV2.objects.filter(competencia=self.competencia, item_contrato=item).delete()
                continue
            MedicaoItemCompetenciaV2.objects.update_or_create(
                competencia=self.competencia,
                item_contrato=item,
                defaults={
                    'quantidade': quantidade,
                    'valor_unitario_aplicado': item.valor_unitario,
                    'observacoes': '',
                },
            )
        self.competencia.medicao_concluida_em = timezone.now()
        self.competencia.save(update_fields=['aplicar_pro_rata', 'medicao_concluida_em', 'atualizado_em'])
        recalcular_competencia_v2(self.competencia)
        messages.success(self.request, 'Medição atualizada com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Medição da competência'
        context['competencia'] = self.competencia
        context['contrato'] = self.competencia.contrato
        context['itens_medicao'] = [
            {'item': item, 'field': context['form'][f'quantidade_{item.pk}']}
            for item in context['form'].itens
        ]
        return context


class CompetenciaAvaliacaoUpdateView(ContratosV2WriteMixin, ContractOperatePermissionMixin, FormView):
    form_class = AvaliacaoCompetenciaV2Form
    template_name = 'contratos_v2/competencia_avaliacao_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.competencia = get_object_or_404(
            CompetenciaPagamentoV2.objects.select_related('contrato'),
            pk=kwargs['competencia_pk'],
        )
        if not self.competencia.contrato.usuario_pode_preencher_avaliacao(request.user):
            return self.deny(self.competencia.contrato, 'Você não pode preencher a avaliação desta competência.')
        if self.competencia.checklist_itens.filter(obrigatorio=True, concluido=False).exists() or not self.competencia.medicao_concluida_em:
            return self.deny(self.competencia.contrato, 'Só é possível partir para a avaliação com checklist e medição concluídos.')
        if not self.competencia.exige_avaliacao:
            return self.deny(self.competencia.contrato, 'Esta competência não exige avaliação de qualidade.')
        if self.competencia.status in {self.competencia.Status.PAGA, self.competencia.Status.CANCELADA}:
            return self.deny(self.competencia.contrato, 'A competência já foi encerrada.')
        self.avaliacao = self.competencia.avaliacao_qualidade_segura
        if self.avaliacao is None and self.competencia.contrato.formulario_avaliacao_ativo:
            self.avaliacao = criar_avaliacao_shell_competencia_v2(self.competencia, self.competencia.contrato.formulario_avaliacao_ativo)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['avaliacao'] = self.avaliacao
        return kwargs

    def form_valid(self, form):
        escala_mapa = {
            Decimal(item['valor']): item['legenda']
            for item in self.avaliacao.formulario_snapshot.get('escala', [])
        }
        for resposta in form.respostas:
            nota = form.cleaned_data.get(f'nota_{resposta.pk}')
            justificativa = form.cleaned_data.get(f'justificativa_{resposta.pk}') or ''
            manifestacao_item = form.cleaned_data.get(f'manifestacao_gestor_item_{resposta.pk}') or ''
            resposta.nota_valor = nota
            resposta.nota_legenda = escala_mapa.get(nota, '')
            resposta.justificativa_fiscal = justificativa
            resposta.manifestacao_gestor_item = manifestacao_item
            resposta.save(
                update_fields=[
                    'nota_valor',
                    'nota_legenda',
                    'justificativa_fiscal',
                    'manifestacao_gestor_item',
                    'atualizado_em',
                ]
            )
        self.avaliacao.observacoes = form.cleaned_data.get('observacoes') or ''
        self.avaliacao.preenchido_por = self.request.user
        # Mantém a competência em avaliação pendente até o gestor preencher as manifestações exigidas.
        self.avaliacao.concluida_em = timezone.now() if avaliacao_v2_esta_concluida(self.avaliacao) else None
        self.avaliacao.save(update_fields=['observacoes', 'preenchido_por', 'concluida_em', 'atualizado_em'])
        recalcular_avaliacao_v2(self.avaliacao)
        if self.avaliacao.concluida_em:
            messages.success(self.request, 'Avaliação concluída com sucesso.')
        else:
            messages.warning(self.request, 'Avaliação salva. A competência permanecerá pendente até o gestor se manifestar nos itens necessários.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Avaliação da competência'
        context['competencia'] = self.competencia
        context['contrato'] = self.competencia.contrato
        context['avaliacao'] = self.avaliacao
        return context


class CompetenciaPagamentoExecuteView(ContratosV2WriteMixin, ContractManagePermissionMixin, UpdateView):
    model = CompetenciaPagamentoV2
    form_class = CompetenciaPagamentoExecucaoV2Form
    template_name = 'contratos_v2/competencia_pagamento_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        response = self.ensure_manage_permission(request, self.object.contrato)
        if response:
            return response
        if not self.object.pode_pagar:
            messages.error(request, 'Só pode partir para o pagamento com checklist, medição e avaliação concluídos.')
            return redirect_contract_detail(self.object.contrato)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['competencia'] = self.object
        return kwargs

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.status = self.object.Status.PAGA
        self.object.autorizado_por = self.request.user
        if not self.object.data_pagamento:
            self.object.data_pagamento = timezone.localdate()
        self.object.save()
        messages.success(self.request, 'Pagamento registrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos_v2:contrato_detail', args=[self.object.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Concluir pagamento'
        context['competencia'] = self.object
        context['contrato'] = self.object.contrato
        return context
