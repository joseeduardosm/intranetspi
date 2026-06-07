# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Entregar as telas, filtros, cadastros e exportações do módulo de contratos.

from io import BytesIO

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from openpyxl import Workbook

from acls.mixins import ACLRequiredMixin

from .forms import (
    AvaliacaoCriterioCompetenciaForm,
    AvaliacaoQualidadeCompetenciaForm,
    ChecklistPagamentoAnexoForm,
    ChecklistPagamentoItemForm,
    ChecklistPagamentoModeloForm,
    CompetenciaPagamentoForm,
    ContratoForm,
    ContratoDetalhamentoItemFormSet,
    ContratoItemForm,
    CriterioAvaliacaoQualidadeForm,
    DocumentoContratoForm,
    EmpresaContratadaForm,
    EventoFinanceiroContratoForm,
    EventoFinanceiroItemForm,
    GrupoAvaliacaoQualidadeForm,
    MedicaoItemCompetenciaForm,
    ModeloAvaliacaoQualidadeForm,
    OcorrenciaContratoAnexoForm,
    OcorrenciaContratoForm,
    ResponsavelEmpresaForm,
    TermoAditivoForm,
)
from .models import (
    AvaliacaoCriterioCompetencia,
    AvaliacaoQualidadeCompetencia,
    ChecklistPagamentoAnexo,
    ChecklistPagamentoItem,
    ChecklistPagamentoModelo,
    CompetenciaPagamento,
    Contrato,
    ContratoDetalhamentoItem,
    ContratoItem,
    CriterioAvaliacaoQualidade,
    DocumentoContrato,
    EmpresaContratada,
    EventoFinanceiroContrato,
    EventoFinanceiroItem,
    GrupoAvaliacaoQualidade,
    MedicaoItemCompetencia,
    ModeloAvaliacaoQualidade,
    OcorrenciaContrato,
    OcorrenciaContratoAnexo,
    ResponsavelEmpresa,
    TermoAditivo,
)
from .services import quantize_money, recalcular_avaliacao, recalcular_competencia


class ContratosAccessMixin(LoginRequiredMixin, ACLRequiredMixin):
    """Base das views do módulo com ACL apontando para o recurso `contratos`."""

    recurso_slug = 'contratos'


class ContratosWriteMixin(ContratosAccessMixin):
    """Exige permissão de modificação para operações de escrita."""

    acl_nivel_minimo = 'MODIFICACAO'


def assign_owner(instance, request):
    """Preenche autoria e última atualização nos modelos que suportam auditoria."""

    if hasattr(instance, 'criado_por') and not instance.criado_por_id:
        instance.criado_por = request.user
    if hasattr(instance, 'atualizado_por'):
        instance.atualizado_por = request.user
    return instance


class ContratosHomeView(ContratosAccessMixin, TemplateView):
    """Tela inicial do módulo com atalhos para áreas principais."""

    template_name = 'contratos/home.html'


class EmpresaListView(ContratosAccessMixin, ListView):
    """Lista empresas contratadas com atalho para manutenção."""

    model = EmpresaContratada
    template_name = 'contratos/empresa_list.html'
    context_object_name = 'empresas'


class EmpresaCreateView(ContratosWriteMixin, CreateView):
    """Cadastro de empresa contratada."""

    model = EmpresaContratada
    form_class = EmpresaContratadaForm
    template_name = 'contratos/form.html'
    success_url = reverse_lazy('contratos:empresa_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova empresa contratada'
        return context


class EmpresaUpdateView(ContratosWriteMixin, UpdateView):
    """Edição dos dados da empresa contratada."""

    model = EmpresaContratada
    form_class = EmpresaContratadaForm
    template_name = 'contratos/form.html'
    success_url = reverse_lazy('contratos:empresa_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar empresa contratada'
        return context


class EmpresaDeleteView(ContratosWriteMixin, DeleteView):
    """Exclusão simples da empresa quando ainda for permitida operacionalmente."""

    model = EmpresaContratada
    template_name = 'contratos/confirm_delete.html'
    success_url = reverse_lazy('contratos:empresa_list')


class ResponsavelEmpresaCreateView(ContratosWriteMixin, CreateView):
    """Adiciona um responsável ao cadastro da empresa."""

    model = ResponsavelEmpresa
    form_class = ResponsavelEmpresaForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.empresa = get_object_or_404(EmpresaContratada, pk=kwargs['empresa_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.empresa = self.empresa
        messages.success(self.request, 'Responsável cadastrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:empresa_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo responsável - {self.empresa.razao_social}'
        return context


class ContratoListView(ContratosAccessMixin, ListView):
    """Listagem principal de contratos com filtros e ordenação básica."""

    model = Contrato
    template_name = 'contratos/contrato_list.html'
    context_object_name = 'contratos'

    def get_queryset(self):
        queryset = (
            Contrato.objects.select_related(
                'empresa_contratada',
                'gestor_contrato',
                'fiscal_administrativo',
                'fiscal_tecnico',
            )
            .prefetch_related('aditivos')
            .all()
        )
        q = (self.request.GET.get('q') or '').strip()
        situacao = (self.request.GET.get('situacao') or '').strip()
        regime = (self.request.GET.get('regime') or '').strip()
        if q:
            queryset = queryset.filter(
                Q(numero_contrato__icontains=q)
                | Q(apelido__icontains=q)
                | Q(objeto__icontains=q)
                | Q(empresa_contratada__razao_social__icontains=q)
            )
        if situacao:
            contratos = [pk for pk in queryset.values_list('pk', flat=True) if Contrato.objects.get(pk=pk).situacao_atual == situacao]
            queryset = queryset.filter(pk__in=contratos)
        if regime:
            contratos = [pk for pk in queryset.values_list('pk', flat=True) if Contrato.objects.get(pk=pk).regime_atual == regime]
            queryset = queryset.filter(pk__in=contratos)
        ordem = self.request.GET.get('ordem') or 'numero_contrato'
        if ordem in {'numero_contrato', 'apelido', 'valor_global', 'data_inicio_vigencia'}:
            queryset = queryset.order_by(ordem, 'id')
        return queryset


class ContratoCreateView(ContratosWriteMixin, CreateView):
    """Cria o contrato principal com vínculos aos usuários internos."""

    model = Contrato
    form_class = ContratoForm
    template_name = 'contratos/form.html'

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo contrato'
        context['show_empresa_atalho'] = True
        if self.request.POST:
            context['detalhamento_formset'] = ContratoDetalhamentoItemFormSet(self.request.POST, prefix='detalhamento')
        else:
            context['detalhamento_formset'] = ContratoDetalhamentoItemFormSet(prefix='detalhamento')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        detalhamento_formset = context['detalhamento_formset']
        if not detalhamento_formset.is_valid():
            return self.form_invalid(form)
        assign_owner(form.instance, self.request)
        self.object = form.save()
        detalhamento_formset.instance = self.object
        detalhamento_formset.save()
        self.object.sync_detalhamento_texto()
        messages.success(self.request, 'Contrato criado com sucesso.')
        return redirect(self.get_success_url())


class ContratoUpdateView(ContratosWriteMixin, UpdateView):
    """Atualiza os dados principais do contrato."""

    model = Contrato
    form_class = ContratoForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        context = self.get_context_data()
        detalhamento_formset = context['detalhamento_formset']
        if not detalhamento_formset.is_valid():
            return self.form_invalid(form)
        assign_owner(form.instance, self.request)
        self.object = form.save()
        detalhamento_formset.instance = self.object
        detalhamento_formset.save()
        self.object.sync_detalhamento_texto()
        messages.success(self.request, 'Contrato atualizado com sucesso.')
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar contrato'
        context['show_empresa_atalho'] = True
        if self.request.POST:
            context['detalhamento_formset'] = ContratoDetalhamentoItemFormSet(
                self.request.POST,
                instance=self.object,
                prefix='detalhamento',
            )
        else:
            context['detalhamento_formset'] = ContratoDetalhamentoItemFormSet(
                instance=self.object,
                prefix='detalhamento',
            )
        return context


class ContratoDeleteView(ContratosWriteMixin, DeleteView):
    """Exclui o contrato quando necessário."""

    model = Contrato
    template_name = 'contratos/confirm_delete.html'
    success_url = reverse_lazy('contratos:contrato_list')


class ContratoDetailView(ContratosAccessMixin, DetailView):
    """Painel operacional do contrato com visão 360º do ciclo de vida."""

    model = Contrato
    template_name = 'contratos/contrato_detail.html'
    context_object_name = 'contrato'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contrato = self.object
        responsaveis = [contrato.gestor_contrato, contrato.fiscal_administrativo, contrato.fiscal_tecnico]
        context.update(
            {
                'item_form': ContratoItemForm(),
                'aditivo_form': TermoAditivoForm(),
                'documento_form': DocumentoContratoForm(),
                'ocorrencia_form': OcorrenciaContratoForm(),
                'competencia_form': CompetenciaPagamentoForm(),
                'checklist_modelo_form': ChecklistPagamentoModeloForm(),
                'modelo_qualidade_form': ModeloAvaliacaoQualidadeForm(),
                'evento_form': EventoFinanceiroContratoForm(),
                'contratos_ativos_empresa': contrato.empresa_contratada.contratos.exclude(pk=contrato.pk).count(),
                'responsaveis_modal': responsaveis,
            }
        )
        context['competencias'] = contrato.competencias.select_related('usuario_responsavel').prefetch_related(
            'checklist_itens',
            'medicoes__item_contrato',
            'avaliacao_qualidade',
        )
        context['medicao_form_factory'] = lambda competencia: MedicaoItemCompetenciaForm(contrato=contrato, prefix=f'medicao-{competencia.pk}')
        context['avaliacao_form_factory'] = lambda competencia: AvaliacaoQualidadeCompetenciaForm(
            contrato=contrato, prefix=f'avaliacao-{competencia.pk}'
        )
        return context


class ContratoChildCreateBase(ContratosWriteMixin, CreateView):
    """Base para cadastros satélite que sempre retornam ao detalhe do contrato."""

    contrato = None

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(Contrato, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.contrato.pk])


class ContratoItemCreateView(ContratoChildCreateBase):
    model = ContratoItem
    form_class = ContratoItemForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Item do contrato cadastrado com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo item - {self.contrato.numero_contrato}'
        return context


class TermoAditivoCreateView(ContratoChildCreateBase):
    model = TermoAditivo
    form_class = TermoAditivoForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Termo aditivo cadastrado com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo termo aditivo - {self.contrato.numero_contrato}'
        return context


class DocumentoContratoCreateView(ContratoChildCreateBase):
    model = DocumentoContrato
    form_class = DocumentoContratoForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        form.instance.usuario_responsavel = self.request.user
        messages.success(self.request, 'Documento incluído com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo documento - {self.contrato.numero_contrato}'
        return context


class OcorrenciaContratoCreateView(ContratoChildCreateBase):
    model = OcorrenciaContrato
    form_class = OcorrenciaContratoForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        form.instance.usuario = self.request.user
        messages.success(self.request, 'Ocorrência registrada com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Nova ocorrência - {self.contrato.numero_contrato}'
        return context


class OcorrenciaAnexoCreateView(ContratosWriteMixin, CreateView):
    model = OcorrenciaContratoAnexo
    form_class = OcorrenciaContratoAnexoForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.ocorrencia = get_object_or_404(OcorrenciaContrato, pk=kwargs['ocorrencia_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.ocorrencia = self.ocorrencia
        messages.success(self.request, 'Anexo da ocorrência adicionado.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.ocorrencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo anexo da ocorrência'
        return context


class CompetenciaCreateView(ContratoChildCreateBase):
    model = CompetenciaPagamento
    form_class = CompetenciaPagamentoForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        form.instance.usuario_responsavel = self.request.user
        messages.success(self.request, 'Competência criada com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Nova competência - {self.contrato.numero_contrato}'
        return context


class ChecklistModeloCreateView(ContratosWriteMixin, CreateView):
    model = ChecklistPagamentoModelo
    form_class = ChecklistPagamentoModeloForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.competencia = get_object_or_404(CompetenciaPagamento, pk=kwargs['competencia_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        contrato = self.competencia.contrato
        form.instance.contrato = contrato
        messages.success(self.request, 'Modelo de checklist cadastrado para o contrato.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo item de checklist - {self.competencia.contrato.numero_contrato}'
        return context


class ChecklistItemToggleView(ContratosWriteMixin, View):
    """Marca e desmarca itens do checklist diretamente na competência."""

    def post(self, request, *args, **kwargs):
        item = get_object_or_404(ChecklistPagamentoItem, pk=kwargs['pk'], competencia_id=kwargs['competencia_pk'])
        item.concluido = not item.concluido
        item.validado_em = timezone.now() if item.concluido else None
        item.save(update_fields=['concluido', 'validado_em'])
        messages.success(request, 'Status do checklist atualizado.')
        return redirect('contratos:contrato_detail', pk=item.competencia.contrato_id)


class ChecklistAnexoCreateView(ContratosWriteMixin, CreateView):
    model = ChecklistPagamentoAnexo
    form_class = ChecklistPagamentoAnexoForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(ChecklistPagamentoItem, pk=kwargs['item_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.item = self.item
        messages.success(self.request, 'Anexo do checklist incluído com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.item.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo anexo do checklist'
        return context


class MedicaoCreateView(ContratosWriteMixin, CreateView):
    model = MedicaoItemCompetencia
    form_class = MedicaoItemCompetenciaForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.competencia = get_object_or_404(CompetenciaPagamento, pk=kwargs['competencia_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['contrato'] = self.competencia.contrato
        return kwargs

    def form_valid(self, form):
        form.instance.competencia = self.competencia
        messages.success(self.request, 'Medição registrada com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova medição da competência'
        return context


class CompetenciaAuthorizeView(ContratosWriteMixin, UpdateView):
    """Tela de confirmação temporizada antes da autorização do pagamento."""

    model = CompetenciaPagamento
    fields = []
    template_name = 'contratos/competencia_authorize.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.pode_liberar:
            messages.error(request, 'A competência ainda possui pendências no checklist obrigatório.')
            return redirect('contratos:contrato_detail', pk=self.object.contrato_id)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.pode_liberar:
            messages.error(request, 'A competência ainda possui pendências no checklist obrigatório.')
            return redirect('contratos:contrato_detail', pk=self.object.contrato_id)
        self.object.confirmada_documentacao_em = timezone.now()
        self.object.status = CompetenciaPagamento.Status.PAGO
        if not self.object.data_efetivacao:
            self.object.data_efetivacao = timezone.localdate()
        self.object.save(update_fields=['confirmada_documentacao_em', 'status', 'data_efetivacao', 'atualizado_em'])
        messages.success(request, 'Pagamento autorizado e registrado como pago.')
        return redirect('contratos:contrato_detail', pk=self.object.contrato_id)


class ModeloQualidadeCreateView(ContratoChildCreateBase):
    model = ModeloAvaliacaoQualidade
    form_class = ModeloAvaliacaoQualidadeForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Modelo de avaliação criado com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo modelo de qualidade - {self.contrato.numero_contrato}'
        return context


class GrupoQualidadeCreateView(ContratosWriteMixin, CreateView):
    model = GrupoAvaliacaoQualidade
    form_class = GrupoAvaliacaoQualidadeForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.modelo = get_object_or_404(ModeloAvaliacaoQualidade, pk=kwargs['modelo_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.modelo = self.modelo
        messages.success(self.request, 'Grupo de avaliação criado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.modelo.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo grupo de avaliação'
        return context


class CriterioQualidadeCreateView(ContratosWriteMixin, CreateView):
    model = CriterioAvaliacaoQualidade
    form_class = CriterioAvaliacaoQualidadeForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.grupo = get_object_or_404(GrupoAvaliacaoQualidade, pk=kwargs['grupo_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.grupo = self.grupo
        messages.success(self.request, 'Critério de avaliação criado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.grupo.modelo.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo critério de avaliação'
        return context


class AvaliacaoCompetenciaCreateView(ContratosWriteMixin, CreateView):
    model = AvaliacaoQualidadeCompetencia
    form_class = AvaliacaoQualidadeCompetenciaForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.competencia = get_object_or_404(CompetenciaPagamento, pk=kwargs['competencia_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['contrato'] = self.competencia.contrato
        return kwargs

    def form_valid(self, form):
        form.instance.competencia = self.competencia
        messages.success(self.request, 'Avaliação da competência criada com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova avaliação da competência'
        return context


class AvaliacaoItemCreateView(ContratosWriteMixin, CreateView):
    model = AvaliacaoCriterioCompetencia
    form_class = AvaliacaoCriterioCompetenciaForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.avaliacao = get_object_or_404(AvaliacaoQualidadeCompetencia, pk=kwargs['avaliacao_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['modelo'] = self.avaliacao.modelo
        return kwargs

    def form_valid(self, form):
        form.instance.avaliacao = self.avaliacao
        messages.success(self.request, 'Pontuação registrada com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.avaliacao.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova pontuação de critério'
        return context


class EventoFinanceiroCreateView(ContratoChildCreateBase):
    model = EventoFinanceiroContrato
    form_class = EventoFinanceiroContratoForm
    template_name = 'contratos/form.html'

    def form_valid(self, form):
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Evento financeiro criado com sucesso.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo evento financeiro - {self.contrato.numero_contrato}'
        return context


class EventoFinanceiroItemCreateView(ContratosWriteMixin, CreateView):
    model = EventoFinanceiroItem
    form_class = EventoFinanceiroItemForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.evento = get_object_or_404(EventoFinanceiroContrato, pk=kwargs['evento_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['contrato'] = self.evento.contrato
        return kwargs

    def form_valid(self, form):
        form.instance.evento = self.evento
        messages.success(self.request, 'Item do evento financeiro registrado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.evento.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo item do evento financeiro'
        return context


class ContratoDashboardView(ContratosAccessMixin, DetailView):
    """Painel gerencial consolidado do contrato com métricas principais."""

    model = Contrato
    template_name = 'contratos/dashboard.html'
    context_object_name = 'contrato'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contrato = self.object
        valor_executado = contrato.competencias.aggregate(total=Sum('valor_liberado')).get('total') or 0
        context['valor_executado'] = quantize_money(valor_executado)
        context['saldo_contratual'] = quantize_money((contrato.valor_global or 0) - context['valor_executado'])
        context['percentual_executado'] = 0
        if contrato.valor_global:
            context['percentual_executado'] = round((context['valor_executado'] / contrato.valor_global) * 100, 2)
        context['contratos_por_empresa'] = (
            Contrato.objects.values('empresa_contratada__razao_social').annotate(total=Count('id')).order_by('-total', 'empresa_contratada__razao_social')[:10]
        )
        context['contratos_por_gestor'] = (
            Contrato.objects.values('gestor_contrato__username').annotate(total=Count('id')).order_by('-total', 'gestor_contrato__username')[:10]
        )
        return context


class OcorrenciaExportXlsxView(ContratosAccessMixin, View):
    """Exporta o diário de bordo em XLSX com cabeçalho por contrato e competência mensal."""

    def get(self, request, *args, **kwargs):
        contrato = get_object_or_404(Contrato, pk=kwargs['pk'])
        ocorrencias = contrato.ocorrencias.order_by('data_registro', 'hora_registro', 'id')
        wb = Workbook()
        ws = wb.active
        ws.title = 'Diário de bordo'
        ws.append(['Número do Contrato', contrato.numero_contrato])
        ws.append(['Objeto', contrato.objeto])
        ws.append(['Competência', timezone.localdate().strftime('%m/%Y')])
        ws.append(['Relação das Ocorrências', ''])
        ws.append([])
        ws.append(['Data', 'Hora', 'Usuário', 'Tipo', 'Descrição'])
        for ocorrencia in ocorrencias:
            usuario = ocorrencia.usuario.get_full_name() if ocorrencia.usuario else ''
            usuario = usuario or (ocorrencia.usuario.username if ocorrencia.usuario else '')
            ws.append(
                [
                    ocorrencia.data_registro.strftime('%d/%m/%Y'),
                    ocorrencia.hora_registro.strftime('%H:%M'),
                    usuario,
                    ocorrencia.tipo_ocorrencia,
                    ocorrencia.descricao,
                ]
            )
        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        response = HttpResponse(
            stream.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="diario_contrato_{slugify(contrato.numero_contrato)}.xlsx"'
        return response
