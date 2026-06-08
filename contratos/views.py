# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Entregar as telas, filtros, cadastros e exportações do módulo de contratos.

from io import BytesIO
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Count, IntegerField, Max, Sum, Value, When
from django.db.models.deletion import ProtectedError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView
from openpyxl import Workbook

from acls.mixins import ACLRequiredMixin

from .forms import (
    AvaliacaoCriterioCompetenciaForm,
    AvaliacaoQualidadeCompetenciaForm,
    ChecklistPagamentoAnexoForm,
    ChecklistPagamentoItemForm,
    ChecklistPagamentoModeloForm,
    CompetenciaPagamentoExecucaoForm,
    CompetenciaMedicaoLoteForm,
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
from .services import full_months_between, quantize_money, recalcular_avaliacao, recalcular_competencia


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


def is_modal_request(request):
    """Indica quando o CRUD deve responder em formato de modal AJAX."""

    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.GET.get('modal') == '1'


def bloquear_fluxo_competencia(request, competencia):
    """Aplica a trava operacional enquanto o checklist padrão ainda não tiver sido replicado."""

    if competencia.aguardando_checklist_padrao:
        messages.error(
            request,
            'A competência está bloqueada até que o checklist padrão do contrato seja cadastrado e replicado.',
        )
        return redirect('contratos:contrato_detail', pk=competencia.contrato_id)
    return None


def usuario_pode_operar_avaliacao_qualidade(contrato, usuario):
    """Libera a avaliação de qualidade apenas para os fiscais quando houver modelo ativo no contrato."""

    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    possui_modelo_ativo = contrato.modelos_qualidade.filter(ativo=True).exists()
    eh_fiscal = usuario.pk in {contrato.fiscal_administrativo_id, contrato.fiscal_tecnico_id}
    return possui_modelo_ativo and eh_fiscal


def serializar_responsavel_interno(label, usuario):
    """Prepara os dados do responsável interno para o modal sem depender de atributos opcionais no template."""

    perfil = getattr(usuario, 'perfil', None)
    foto = getattr(perfil, 'foto', None)
    foto_url = ''
    if foto and getattr(foto, 'name', ''):
        try:
            foto_url = foto.url
        except ValueError:
            foto_url = ''
    return {
        'label': label,
        'nome': getattr(perfil, 'nome_completo', None) or usuario.get_full_name() or usuario.username,
        'foto_url': foto_url,
        'cargo': getattr(perfil, 'cargo', '') or '-',
        'setor': getattr(perfil, 'setor', '') or '-',
        'email': usuario.email or '-',
        'ramal': getattr(perfil, 'ramal', '') or '-',
        'celular': getattr(perfil, 'celular', '') or '',
        'whatsapp': perfil.whatsapp_url if perfil else '',
        'local': perfil.andar_bloco_display if perfil else '-',
        'nome_link': usuario.get_full_name() or usuario.username,
    }


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

    def render_to_response(self, context, **response_kwargs):
        if is_modal_request(self.request):
            return render(self.request, 'contratos/partials/empresa_modal_form.html', context, **response_kwargs)
        return super().render_to_response(context, **response_kwargs)

    def form_valid(self, form):
        self.object = form.save()
        if is_modal_request(self.request):
            return JsonResponse(
                {
                    'success': True,
                    'empresa': {
                        'id': self.object.pk,
                        'label': self.object.razao_social,
                        'cnpj': self.object.cnpj,
                    },
                }
            )
        messages.success(self.request, 'Empresa cadastrada com sucesso.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova empresa contratada'
        context['modal_mode'] = is_modal_request(self.request)
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
    """Listagem principal de contratos com filtros e ordenação em todas as colunas visíveis."""

    model = Contrato
    template_name = 'contratos/contrato_list.html'
    context_object_name = 'contratos'
    campos_ordenaveis = (
        'numero_contrato',
        'apelido',
        'empresa',
        'situacao',
        'prazo_atual',
        'periodo_acumulado',
        'data_final',
        'regime',
        'valor_global',
    )

    def _ordenacao_valor(self, contrato, campo):
        """Traduz cada coluna da tabela em uma chave comparável de ordenação."""

        hoje = timezone.localdate()
        data_final = contrato.data_final_vigencia or hoje
        fim_prazo_atual = data_final if hoje > data_final else hoje
        meses_prazo_atual = full_months_between(contrato.data_inicio_vigencia, fim_prazo_atual)
        fim_periodo_acumulado = min(hoje, data_final)
        meses_periodo_acumulado = full_months_between(contrato.data_inicio_vigencia, fim_periodo_acumulado)
        situacao_rank = {
            Contrato.Situacao.VIGENTE: 1,
            Contrato.Situacao.A_VENCER: 2,
            Contrato.Situacao.SUSPENSO: 3,
            Contrato.Situacao.ENCERRADO: 4,
        }
        regime_rank = {
            Contrato.Regime.ORDINARIO: 1,
            Contrato.Regime.EXCEPCIONAL: 2,
            Contrato.Regime.EMERGENCIAL: 3,
        }
        mapa = {
            'numero_contrato': contrato.numero_contrato or '',
            'apelido': contrato.apelido or '',
            'empresa': contrato.empresa_contratada.razao_social if contrato.empresa_contratada_id else '',
            'situacao': (situacao_rank.get(contrato.situacao_atual, 99), contrato.situacao_atual_display),
            'prazo_atual': (meses_prazo_atual, contrato.vigencia_total_meses, contrato.numero_contrato or ''),
            'periodo_acumulado': (meses_periodo_acumulado, int(contrato.vigencia_maxima_meses or 0), contrato.numero_contrato or ''),
            'data_final': (data_final or contrato.data_inicio_vigencia, contrato.numero_contrato or ''),
            'regime': (regime_rank.get(contrato.regime_atual, 99), contrato.regime_atual_display),
            'valor_global': (contrato.valor_global or 0, contrato.numero_contrato or ''),
        }
        return mapa[campo]

    def _ordenar_contratos(self, contratos):
        """Aplica ordenação crescente ou decrescente conforme os parâmetros da querystring."""

        campo = (self.request.GET.get('ordem') or 'numero_contrato').strip()
        direcao = (self.request.GET.get('direcao') or 'asc').strip().lower()
        if campo not in self.campos_ordenaveis:
            campo = 'numero_contrato'
        if direcao not in {'asc', 'desc'}:
            direcao = 'asc'
        return sorted(contratos, key=lambda contrato: self._ordenacao_valor(contrato, campo), reverse=direcao == 'desc')

    def get_queryset(self):
        queryset = list(
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
            queryset = [
                contrato for contrato in queryset
                if (
                    q.lower() in (contrato.numero_contrato or '').lower()
                    or q.lower() in (contrato.apelido or '').lower()
                    or q.lower() in (contrato.objeto or '').lower()
                    or q.lower() in (contrato.empresa_contratada.razao_social or '').lower()
                )
            ]
        if situacao:
            queryset = [contrato for contrato in queryset if contrato.situacao_atual == situacao]
        if regime:
            queryset = [contrato for contrato in queryset if contrato.regime_atual == regime]
        return self._ordenar_contratos(queryset)

    def get_context_data(self, **kwargs):
        """Expõe o estado de ordenação para renderizar cabeçalhos clicáveis com alternância de direção."""

        context = super().get_context_data(**kwargs)
        ordem_atual = (self.request.GET.get('ordem') or 'numero_contrato').strip()
        direcao_atual = (self.request.GET.get('direcao') or 'asc').strip().lower()
        if ordem_atual not in self.campos_ordenaveis:
            ordem_atual = 'numero_contrato'
        if direcao_atual not in {'asc', 'desc'}:
            direcao_atual = 'asc'

        base_params = self.request.GET.copy()
        base_params.pop('ordem', None)
        base_params.pop('direcao', None)
        ordenacao_links = {}
        for campo in self.campos_ordenaveis:
            params = base_params.copy()
            params['ordem'] = campo
            params['direcao'] = 'desc' if campo == ordem_atual and direcao_atual == 'asc' else 'asc'
            ordenacao_links[campo] = {
                'querystring': urlencode(params, doseq=True),
                'ativa': campo == ordem_atual,
                'direcao': direcao_atual if campo == ordem_atual else '',
            }

        context['ordem_atual'] = ordem_atual
        context['direcao_atual'] = direcao_atual
        context['ordenacao_links'] = ordenacao_links
        return context


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

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            messages.error(
                request,
                'Este contrato não pode ser excluído porque ainda possui vínculos dependentes, como avaliações, competências ou documentos relacionados.',
            )
            return redirect('contratos:contrato_detail', pk=self.object.pk)


class ContratoDetailView(ContratosAccessMixin, DetailView):
    """Painel operacional do contrato com visão 360º do ciclo de vida."""

    model = Contrato
    template_name = 'contratos/contrato_detail.html'
    context_object_name = 'contrato'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        contrato = self.object
        responsaveis = [
            serializar_responsavel_interno('Gestor', contrato.gestor_contrato),
            serializar_responsavel_interno('Fiscal administrativo', contrato.fiscal_administrativo),
            serializar_responsavel_interno('Fiscal técnico', contrato.fiscal_tecnico),
        ]
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
                'responsaveis_internos': responsaveis,
                'mostrar_avaliacao_qualidade_competencia': usuario_pode_operar_avaliacao_qualidade(contrato, self.request.user),
            }
        )
        context['competencias'] = (
            contrato.competencias.annotate(
                # Competências já pagas ficam por último, preservando a leitura cronológica das demais.
                ordem_pagamento=Case(
                    When(status=CompetenciaPagamento.Status.PAGO, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .select_related('usuario_responsavel')
            .prefetch_related(
                'checklist_itens',
                'medicoes__item_contrato',
                'avaliacao_qualidade',
            )
            .order_by('ordem_pagamento', 'periodo_inicio', 'periodo_fim', 'id')
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

    def get_initial(self):
        initial = super().get_initial()
        # Sugere a próxima ordem livre para reduzir retrabalho no cadastro manual.
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo item - {self.contrato.numero_contrato}'
        return context


class ContratoItemUpdateView(ContratosWriteMixin, UpdateView):
    """Edita um item existente do contrato."""

    model = ContratoItem
    form_class = ContratoItemForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(Contrato, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ContratoItem.objects.filter(contrato=self.contrato)

    def form_valid(self, form):
        conflito = self.contrato.itens.exclude(pk=self.object.pk).filter(ordem=form.instance.ordem).exists()
        if conflito:
            form.add_error('ordem', 'Já existe um item com essa numeração neste contrato.')
            return self.form_invalid(form)
        messages.success(self.request, 'Item do contrato atualizado com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.contrato.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar item - {self.contrato.numero_contrato}'
        return context


class ContratoItemDeleteView(ContratosWriteMixin, DeleteView):
    """Exclui um item do contrato e retorna ao detalhe do contrato."""

    model = ContratoItem
    template_name = 'contratos/confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.contrato = get_object_or_404(Contrato, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ContratoItem.objects.filter(contrato=self.contrato)

    def get_success_url(self):
        messages.success(self.request, 'Item do contrato excluído com sucesso.')
        return reverse('contratos:contrato_detail', args=[self.contrato.pk])


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
        # Diferencia lançamentos excepcionais feitos manualmente da grade automática da vigência.
        form.instance.gerada_automaticamente = False
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
        self.contrato = get_object_or_404(Contrato, pk=kwargs['contrato_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # O checklist padrão pertence ao contrato e depois é replicado nas competências.
        form.instance.contrato = self.contrato
        messages.success(self.request, 'Modelo de checklist cadastrado para o contrato.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.contrato.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo item de checklist - {self.contrato.numero_contrato}'
        return context


class ChecklistItemToggleView(ContratosWriteMixin, View):
    """Marca e desmarca itens do checklist diretamente na competência."""

    def post(self, request, *args, **kwargs):
        item = get_object_or_404(ChecklistPagamentoItem, pk=kwargs['pk'], competencia_id=kwargs['competencia_pk'])
        bloqueio = bloquear_fluxo_competencia(request, item.competencia)
        if bloqueio:
            return bloqueio
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
        bloqueio = bloquear_fluxo_competencia(request, self.item.competencia)
        if bloqueio:
            return bloqueio
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        if is_modal_request(self.request):
            return render(self.request, 'contratos/partials/checklist_anexo_modal_form.html', context, **response_kwargs)
        return super().render_to_response(context, **response_kwargs)

    def form_valid(self, form):
        existente = self.item.anexo_principal
        if existente:
            existente.arquivo = form.cleaned_data['arquivo']
            existente.nome_exibicao = ''
            existente.save(update_fields=['arquivo', 'nome_exibicao'])
            self.object = existente
            if is_modal_request(self.request):
                return JsonResponse({'success': True})
            messages.success(self.request, 'Anexo do checklist atualizado com sucesso.')
            return redirect(self.get_success_url())
        form.instance.item = self.item
        form.instance.nome_exibicao = ''
        if is_modal_request(self.request):
            self.object = form.save()
            return JsonResponse({'success': True})
        messages.success(self.request, 'Anexo do checklist incluído com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.item.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo anexo do checklist'
        context['item'] = self.item
        return context


class ChecklistAnexoUpdateView(ContratosWriteMixin, UpdateView):
    """Permite substituir o arquivo atual do checklist usando a tela padrão do módulo."""

    model = ChecklistPagamentoAnexo
    form_class = ChecklistPagamentoAnexoForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(ChecklistPagamentoItem, pk=kwargs['item_pk'])
        bloqueio = bloquear_fluxo_competencia(request, self.item.competencia)
        if bloqueio:
            return bloqueio
        if not self.item.anexo_principal:
            messages.error(request, 'Este item ainda não possui anexo para edição.')
            return redirect('contratos:contrato_detail', pk=self.item.competencia.contrato_id)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.item.anexo_principal

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.item.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar anexo do checklist'
        return context


class ChecklistAnexoDeleteView(ContratosWriteMixin, View):
    """Remove o anexo do checklist e devolve o item ao estado pendente quando necessário."""

    def post(self, request, *args, **kwargs):
        item = get_object_or_404(ChecklistPagamentoItem, pk=kwargs['item_pk'])
        bloqueio = bloquear_fluxo_competencia(request, item.competencia)
        if bloqueio:
            return bloqueio
        anexo = item.anexo_principal
        if anexo:
            anexo.delete()
            messages.success(request, 'Anexo removido com sucesso.')
        else:
            messages.error(request, 'Não há anexo para limpar neste item.')
        return redirect('contratos:contrato_detail', pk=item.competencia.contrato_id)


class MedicaoCreateView(ContratosWriteMixin, FormView):
    """Tela mensal de medição que lista os itens do contrato para preenchimento das quantidades."""

    form_class = CompetenciaMedicaoLoteForm
    template_name = 'contratos/medicao_lote_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.competencia = get_object_or_404(CompetenciaPagamento, pk=kwargs['competencia_pk'])
        bloqueio = bloquear_fluxo_competencia(request, self.competencia)
        if bloqueio:
            return bloqueio
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['contrato'] = self.competencia.contrato
        kwargs['competencia'] = self.competencia
        return kwargs

    def form_valid(self, form):
        # Como a competência já delimita o mês de apuração, o usuário informa apenas as quantidades medidas por item.
        for item in form.itens:
            quantidade = form.cleaned_data.get(f'quantidade_{item.pk}')
            if quantidade in (None, ''):
                continue
            if quantidade == 0:
                MedicaoItemCompetencia.objects.filter(competencia=self.competencia, item_contrato=item).delete()
                continue
            MedicaoItemCompetencia.objects.update_or_create(
                competencia=self.competencia,
                item_contrato=item,
                defaults={
                    'quantidade': quantidade,
                    'valor_unitario_aplicado': item.valor_unitario,
                    'observacoes': '',
                },
            )
        messages.success(self.request, 'Medições da competência atualizadas com sucesso.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.competencia.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Medição da competência'
        context['competencia'] = self.competencia
        context['contrato'] = self.competencia.contrato
        context['itens_medicao'] = [
            {
                'item': item,
                'field': context['form'][f'quantidade_{item.pk}'],
            }
            for item in context['form'].itens
        ]
        return context


class CompetenciaAuthorizeView(ContratosWriteMixin, UpdateView):
    """Tela de confirmação temporizada antes da autorização do pagamento."""

    model = CompetenciaPagamento
    fields = []
    template_name = 'contratos/competencia_authorize.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        bloqueio = bloquear_fluxo_competencia(request, self.object)
        if bloqueio:
            return bloqueio
        if not self.object.pode_liberar:
            messages.error(request, 'A competência ainda possui pendências no checklist obrigatório.')
            return redirect('contratos:contrato_detail', pk=self.object.contrato_id)
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        bloqueio = bloquear_fluxo_competencia(request, self.object)
        if bloqueio:
            return bloqueio
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


class CompetenciaPagamentoExecutarView(ContratosWriteMixin, UpdateView):
    """Recebe os anexos finais do pagamento e encerra a competência como paga."""

    model = CompetenciaPagamento
    form_class = CompetenciaPagamentoExecucaoForm
    template_name = 'contratos/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        bloqueio = bloquear_fluxo_competencia(request, self.object)
        if bloqueio:
            return bloqueio
        if not self.object.pode_liberar:
            messages.error(request, 'A competência ainda possui pendências no checklist obrigatório.')
            return redirect('contratos:contrato_detail', pk=self.object.contrato_id)
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):
        if is_modal_request(self.request):
            return render(self.request, 'contratos/partials/competencia_pagamento_modal_form.html', context, **response_kwargs)
        return super().render_to_response(context, **response_kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.confirmada_documentacao_em = timezone.now()
        self.object.status = CompetenciaPagamento.Status.PAGO
        self.object.usuario_responsavel = self.request.user
        if not self.object.data_efetivacao:
            self.object.data_efetivacao = timezone.localdate()
        self.object.save()
        if is_modal_request(self.request):
            return JsonResponse({'success': True})
        messages.success(self.request, 'Pagamento anexado e competência registrada como paga.')
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse('contratos:contrato_detail', args=[self.object.contrato_id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Inserir pagamento'
        context['competencia'] = self.object
        return context


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
        if not usuario_pode_operar_avaliacao_qualidade(self.competencia.contrato, request.user):
            messages.error(request, 'A avaliação de qualidade desta competência só fica disponível para os fiscais após o cadastro do modelo pelo gestor.')
            return redirect('contratos:contrato_detail', pk=self.competencia.contrato_id)
        bloqueio = bloquear_fluxo_competencia(request, self.competencia)
        if bloqueio:
            return bloqueio
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
        if not usuario_pode_operar_avaliacao_qualidade(self.avaliacao.competencia.contrato, request.user):
            messages.error(request, 'A avaliação de qualidade desta competência só fica disponível para os fiscais após o cadastro do modelo pelo gestor.')
            return redirect('contratos:contrato_detail', pk=self.avaliacao.competencia.contrato_id)
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
