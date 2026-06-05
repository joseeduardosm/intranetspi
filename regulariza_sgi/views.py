# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Controlar telas de imóveis, anexos, processos SEI e eventos processuais.

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import ImovelAnexoForm, ImovelForm, ManifestacaoForm, ProcessoSEIForm, ProtocoloForm, ProrrogacaoForm
from .models import CicloProcessual, Imovel, ImovelAnexo, ImovelProcessoSEI
from .services import MUNICIPIOS_POR_UF, compute_timeline_context, create_followup_cycle, current_cycle, sync_ciclo


class RegularizaSgiAccessMixin(LoginRequiredMixin):
    """Exige login para acessar o módulo Regulariza SGI."""

    login_url = reverse_lazy('login')


class RegularizaSgiHomeView(RegularizaSgiAccessMixin, TemplateView):
    """Exibe a página inicial do módulo com atalhos principais."""

    template_name = 'regulariza_sgi/home.html'


class ImovelListView(RegularizaSgiAccessMixin, ListView):
    """Lista imóveis com busca ampla e indicadores de timeline/CADIN."""

    model = Imovel
    template_name = 'regulariza_sgi/imovel_list.html'
    context_object_name = 'imoveis'
    paginate_by = 20

    def get_queryset(self):
        queryset = Imovel.objects.all()
        # A busca percorre dados cadastrais, processos SEI e anexos relacionados.
        term = self.request.GET.get('q', '').strip()
        if term:
            queryset = queryset.filter(
                Q(inscricao_imobiliaria__icontains=term)
                | Q(matricula__icontains=term)
                | Q(processo_judicial__icontains=term)
                | Q(numero_sgi__icontains=term)
                | Q(uf__icontains=term)
                | Q(municipio__icontains=term)
                | Q(logradouro__icontains=term)
                | Q(bairro__icontains=term)
                | Q(numero__icontains=term)
                | Q(area__icontains=term)
                | Q(exercicio_cadin__icontains=term)
                | Q(notificacao_cadin_municipal__icontains=term)
                | Q(processos_sei__numero_sei__icontains=term)
                | Q(processos_sei__link_sei__icontains=term)
                | Q(anexos__nome_exibicao__icontains=term)
            ).distinct()
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Cada imóvel recebe uma timeline calculada para colorir a linha da tabela.
        for imovel in context['imoveis']:
            imovel.timeline = compute_timeline_context(imovel)
        context['q'] = self.request.GET.get('q', '').strip()
        return context


class ImovelCreateView(RegularizaSgiAccessMixin, CreateView):
    """Cadastra um imóvel e direciona para o detalhe após salvar."""

    model = Imovel
    form_class = ImovelForm
    template_name = 'regulariza_sgi/imovel_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Imóvel cadastrado.')
        return reverse('regulariza_sgi:imovel_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Novo imóvel'
        context['municipios_json'] = MUNICIPIOS_POR_UF
        return context


class ImovelUpdateView(RegularizaSgiAccessMixin, UpdateView):
    """Atualiza dados cadastrais do imóvel."""

    model = Imovel
    form_class = ImovelForm
    template_name = 'regulariza_sgi/imovel_form.html'

    def get_success_url(self):
        messages.success(self.request, 'Imóvel atualizado.')
        return reverse('regulariza_sgi:imovel_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Editar imóvel'
        context['municipios_json'] = MUNICIPIOS_POR_UF
        return context


class ImovelDeleteView(RegularizaSgiAccessMixin, DeleteView):
    """Remove um imóvel após confirmação."""

    model = Imovel
    template_name = 'regulariza_sgi/confirm_delete.html'
    success_url = reverse_lazy('regulariza_sgi:imovel_list')

    def form_valid(self, form):
        messages.success(self.request, 'Imóvel excluído.')
        return super().form_valid(form)


class ImovelDetailView(RegularizaSgiAccessMixin, DetailView):
    """Exibe resumo do imóvel, timeline, histórico e formulários de ações do ciclo."""

    model = Imovel
    template_name = 'regulariza_sgi/imovel_detail.html'
    context_object_name = 'imovel'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # O detalhe concentra formulários de eventos porque eles dependem do ciclo atual.
        imovel = self.object
        ciclo = current_cycle(imovel)
        timeline = compute_timeline_context(imovel)
        context['timeline'] = timeline
        context['ciclo_atual'] = ciclo
        context['sei_form'] = kwargs.get('sei_form') or ProcessoSEIForm()
        context['anexo_form'] = kwargs.get('anexo_form') or ImovelAnexoForm()
        context['protocolo_form'] = kwargs.get('protocolo_form') or ProtocoloForm()
        context['prorrogacao_form'] = kwargs.get('prorrogacao_form') or ProrrogacaoForm()
        context['manifestacao_form'] = kwargs.get('manifestacao_form') or ManifestacaoForm()
        context['pode_registrar_protocolo'] = bool(ciclo and not ciclo.data_protocolo)
        context['pode_registrar_prorrogacao'] = bool(ciclo and ciclo.data_protocolo and not ciclo.data_manifestacao)
        context['pode_registrar_manifestacao'] = bool(ciclo and ciclo.data_protocolo and not ciclo.data_manifestacao)
        context['pode_reiniciar_ciclo'] = bool(ciclo and ciclo.resultado in CicloProcessual.Resultado.values)
        context['proximo_ciclo_tipo'] = self._proximo_ciclo_tipo(ciclo)
        return context

    def _proximo_ciclo_tipo(self, ciclo):
        """Define se o próximo ciclo será renovação ou contrarrazão."""

        if not ciclo or not ciclo.resultado:
            return ''
        if ciclo.resultado == CicloProcessual.Resultado.DEFERIDO:
            return CicloProcessual.Tipo.RENOVACAO
        return CicloProcessual.Tipo.CONTRARRAZAO


class ImovelChildMixin(RegularizaSgiAccessMixin):
    """Mixin para recursos filhos que sempre pertencem a um imóvel."""

    parent_model = Imovel
    parent_kwarg = 'imovel_pk'
    parent_context_name = 'imovel'

    def dispatch(self, request, *args, **kwargs):
        # Carrega o imóvel pai antes de operar processos SEI ou anexos.
        self.imovel = get_object_or_404(self.parent_model, pk=kwargs[self.parent_kwarg])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[self.parent_context_name] = self.imovel
        return context

    def get_success_url(self):
        return reverse('regulariza_sgi:imovel_detail', args=[self.imovel.pk])


class ProcessoSEICreateView(ImovelChildMixin, CreateView):
    """Adiciona um processo SEI ao imóvel."""

    model = ImovelProcessoSEI
    form_class = ProcessoSEIForm
    template_name = 'regulariza_sgi/resource_form.html'

    def form_valid(self, form):
        form.instance.imovel = self.imovel
        messages.success(self.request, 'Processo SEI adicionado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Novo processo SEI'
        return context


class ProcessoSEIUpdateView(ImovelChildMixin, UpdateView):
    """Edita um processo SEI vinculado ao imóvel atual."""

    model = ImovelProcessoSEI
    form_class = ProcessoSEIForm
    template_name = 'regulariza_sgi/resource_form.html'

    def get_queryset(self):
        return ImovelProcessoSEI.objects.filter(imovel=self.imovel)

    def form_valid(self, form):
        messages.success(self.request, 'Processo SEI atualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Editar processo SEI'
        return context


class ProcessoSEIDeleteView(ImovelChildMixin, DeleteView):
    """Remove um processo SEI do imóvel atual."""

    model = ImovelProcessoSEI
    template_name = 'regulariza_sgi/confirm_delete.html'

    def get_queryset(self):
        return ImovelProcessoSEI.objects.filter(imovel=self.imovel)

    def get_success_url(self):
        messages.success(self.request, 'Processo SEI excluído.')
        return reverse('regulariza_sgi:imovel_detail', args=[self.imovel.pk])


class AnexoCreateView(ImovelChildMixin, CreateView):
    """Adiciona um anexo ao imóvel."""

    model = ImovelAnexo
    form_class = ImovelAnexoForm
    template_name = 'regulariza_sgi/resource_form.html'

    def form_valid(self, form):
        form.instance.imovel = self.imovel
        messages.success(self.request, 'Anexo adicionado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Novo anexo'
        return context


class AnexoUpdateView(ImovelChildMixin, UpdateView):
    """Edita metadados ou arquivo de um anexo do imóvel."""

    model = ImovelAnexo
    form_class = ImovelAnexoForm
    template_name = 'regulariza_sgi/resource_form.html'

    def get_queryset(self):
        return ImovelAnexo.objects.filter(imovel=self.imovel)

    def form_valid(self, form):
        messages.success(self.request, 'Anexo atualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form_title'] = 'Editar anexo'
        return context


class AnexoDeleteView(ImovelChildMixin, DeleteView):
    """Remove um anexo do imóvel atual."""

    model = ImovelAnexo
    template_name = 'regulariza_sgi/confirm_delete.html'

    def get_queryset(self):
        return ImovelAnexo.objects.filter(imovel=self.imovel)

    def get_success_url(self):
        messages.success(self.request, 'Anexo excluído.')
        return reverse('regulariza_sgi:imovel_detail', args=[self.imovel.pk])


class CurrentCycleMutationView(RegularizaSgiAccessMixin, View):
    """Base para ações que alteram o ciclo processual mais recente do imóvel."""

    form_class = None

    def dispatch(self, request, *args, **kwargs):
        # A ação só é possível quando há ciclo atual criado pelo sinal do imóvel.
        self.imovel = get_object_or_404(Imovel, pk=kwargs['pk'])
        self.ciclo = current_cycle(self.imovel)
        if not self.ciclo:
            raise Http404('Ciclo processual não encontrado.')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.form_class(request.POST)
        if form.is_valid():
            return self.form_valid(form)
        # Em caso de erro, reaproveita o detalhe com o formulário inválido no contexto correto.
        view = ImovelDetailView()
        view.request = request
        view.object = self.imovel
        kwargs = {self.context_form_name: form}
        return view.render_to_response(view.get_context_data(**kwargs))


class RegistrarProtocoloView(CurrentCycleMutationView):
    """Registra protocolo e inicia a contagem de manifestação prevista."""

    form_class = ProtocoloForm
    context_form_name = 'protocolo_form'

    def form_valid(self, form):
        if self.ciclo.data_protocolo:
            messages.error(self.request, 'O protocolo deste ciclo já foi registrado.')
            return redirect('regulariza_sgi:imovel_detail', pk=self.imovel.pk)
        self.ciclo.numero_protocolo = form.cleaned_data['numero_protocolo']
        self.ciclo.data_protocolo = form.cleaned_data['data_protocolo']
        self.ciclo.prazo_resposta_dias = form.cleaned_data['prazo_resposta_dias']
        sync_ciclo(self.ciclo, usuario=self.request.user.username, tipo_evento='PROTOCOLO')
        messages.success(self.request, 'Protocolo registrado.')
        return redirect('regulariza_sgi:imovel_detail', pk=self.imovel.pk)


class RegistrarProrrogacaoView(CurrentCycleMutationView):
    """Acrescenta prorrogação ao prazo de resposta do ciclo atual."""

    form_class = ProrrogacaoForm
    context_form_name = 'prorrogacao_form'

    def form_valid(self, form):
        if not self.ciclo.data_protocolo or self.ciclo.data_manifestacao:
            messages.error(self.request, 'A prorrogação só pode ser registrada após o protocolo e antes da manifestação.')
            return redirect('regulariza_sgi:imovel_detail', pk=self.imovel.pk)
        self.ciclo.prorrogacao_dias += form.cleaned_data['prorrogacao_dias']
        self.ciclo.data_prorrogacao = form.cleaned_data['data_prorrogacao']
        sync_ciclo(self.ciclo, usuario=self.request.user.username, tipo_evento='PRORROGACAO')
        messages.success(self.request, 'Prorrogação registrada.')
        return redirect('regulariza_sgi:imovel_detail', pk=self.imovel.pk)


class RegistrarManifestacaoView(CurrentCycleMutationView):
    """Registra deferimento ou indeferimento e recalcula prazos derivados."""

    form_class = ManifestacaoForm
    context_form_name = 'manifestacao_form'

    def form_valid(self, form):
        if not self.ciclo.data_protocolo or self.ciclo.data_manifestacao:
            messages.error(self.request, 'A manifestação só pode ser registrada após o protocolo.')
            return redirect('regulariza_sgi:imovel_detail', pk=self.imovel.pk)
        self.ciclo.resultado = form.cleaned_data['resultado']
        self.ciclo.data_manifestacao = form.cleaned_data['data_manifestacao']
        self.ciclo.prazo_imunidade_anos = form.cleaned_data['prazo_imunidade_anos']
        tipo_evento = 'DEFERIMENTO' if self.ciclo.resultado == CicloProcessual.Resultado.DEFERIDO else 'INDEFERIMENTO'
        sync_ciclo(self.ciclo, usuario=self.request.user.username, tipo_evento=tipo_evento)
        messages.success(self.request, 'Manifestação registrada.')
        return redirect('regulariza_sgi:imovel_detail', pk=self.imovel.pk)


class ReiniciarCicloView(RegularizaSgiAccessMixin, View):
    """Cria ciclo posterior após resultado do ciclo atual."""

    def post(self, request, pk):
        imovel = get_object_or_404(Imovel, pk=pk)
        ciclo = current_cycle(imovel)
        if not ciclo or not ciclo.resultado:
            messages.error(request, 'Ainda não há resultado para reiniciar o fluxo.')
            return redirect('regulariza_sgi:imovel_detail', pk=imovel.pk)
        tipo = CicloProcessual.Tipo.RENOVACAO if ciclo.resultado == CicloProcessual.Resultado.DEFERIDO else CicloProcessual.Tipo.CONTRARRAZAO
        create_followup_cycle(imovel, tipo, usuario=request.user.username)
        messages.success(request, 'Novo ciclo criado. Registre o protocolo para continuar.')
        return redirect('regulariza_sgi:imovel_detail', pk=imovel.pk)
