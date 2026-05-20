from io import BytesIO

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Max
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import (
    DfdCreateForm,
    DfdItemTabelaForm,
    DfdSecaoForm,
    EtpTicCreateForm,
    EtpTicSecaoForm,
    ItemMoveForm,
    ItemTRForm,
    SessaoTRForm,
    TabelaItemLinhaForm,
    TermoReferenciaForm,
)
from .models import Dfd, DfdItemTabela, EtpTic, ItemTR, SessaoTR, TabelaItemLinha, TermoReferencia
from .services import (
    DFD_SECOES,
    DFD_SECOES_MAP,
    ETP_TIC_SECOES,
    ETP_TIC_SECOES_MAP,
    build_item_rows,
    item_parent_for_tipo,
    build_termo_tree,
    duplicate_item,
    dfd_status_por_secao,
    etp_status_por_secao,
    move_item,
    next_ordem_item,
    next_ordem_sessao,
    normalize_items,
    normalize_sessoes,
    quantidade_text,
    red_mark_segments,
    render_dfd_sections,
    render_etp_sections,
)


def item_focus_url(item):
    return f"{reverse('licitacoes:tr_detail', args=[item.sessao.termo.pk])}#item-{item.pk}"


def sessao_focus_url(sessao):
    return f"{reverse('licitacoes:tr_detail', args=[sessao.termo.pk])}#sessao-{sessao.pk}"


def item_delete_return_url(item):
    siblings = list(item.sessao.itens.filter(parent_id=item.parent_id).exclude(pk=item.pk).order_by('ordem', 'id'))
    next_item = next((sibling for sibling in siblings if (sibling.ordem, sibling.id) > (item.ordem, item.id)), None)
    if next_item:
        return item_focus_url(next_item)

    previous_items = [sibling for sibling in siblings if (sibling.ordem, sibling.id) < (item.ordem, item.id)]
    if previous_items:
        return item_focus_url(previous_items[-1])

    if item.parent:
        return item_focus_url(item.parent)

    return sessao_focus_url(item.sessao)


def item_indice(item):
    for row in build_item_rows(item.sessao):
        if row['item'].id == item.id:
            return row['indice']
    return ''


def tabela_item_url(item):
    return f"{reverse('licitacoes:tr_detail', args=[item.sessao.termo.pk])}#tabela-itens-{item.pk}"


def get_item_tabela_1_1(sessao_pk, item_pk):
    item = get_object_or_404(ItemTR, pk=item_pk, sessao__termo__sessoes__id=sessao_pk)
    if item_indice(item) != '1.1':
        raise Http404('Tabela disponivel apenas para o item 1.1.')
    return item


class SuperuserRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class LicitacoesHomeView(SuperuserRequiredMixin, TemplateView):
    template_name = 'licitacoes/home.html'


class EtpTicListView(SuperuserRequiredMixin, ListView):
    model = EtpTic
    template_name = 'licitacoes/etp_list.html'
    context_object_name = 'etps'


class EtpTicCreateView(SuperuserRequiredMixin, CreateView):
    model = EtpTic
    form_class = EtpTicCreateForm
    template_name = 'licitacoes/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo ETP TIC'
        context['voltar_url'] = reverse('licitacoes:etp_list')
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.declaracao_viabilidade = EtpTic.DECLARACAO_PADRAO
        self.object.save()
        return redirect(f"{reverse('licitacoes:etp_edit', args=[self.object.pk])}?secao=1")


class EtpTicEditView(SuperuserRequiredMixin, UpdateView):
    model = EtpTic
    form_class = EtpTicSecaoForm
    template_name = 'licitacoes/etp_edit.html'
    context_object_name = 'etp'

    def _secao_numero(self):
        try:
            numero = int(self.request.GET.get('secao') or self.object.secao_atual or 1)
        except (TypeError, ValueError):
            numero = 1
        return numero if numero in ETP_TIC_SECOES_MAP else 1

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['section_fields'] = ETP_TIC_SECOES_MAP[self._secao_numero()]['campos']
        return kwargs

    def form_valid(self, form):
        etp = form.save(commit=False)
        secao = self._secao_numero()
        acao = self.request.POST.get('_acao', 'salvar')
        if acao == 'proximo':
            etp.secao_atual = min(secao + 1, 18)
        elif acao == 'anterior':
            etp.secao_atual = max(secao - 1, 1)
        else:
            etp.secao_atual = secao
        etp.save()
        return redirect(f"{reverse('licitacoes:etp_edit', args=[etp.pk])}?secao={etp.secao_atual}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        secao_numero = self._secao_numero()
        status = etp_status_por_secao(self.object)
        context['secao_numero'] = secao_numero
        context['secao_atual'] = ETP_TIC_SECOES_MAP[secao_numero]
        context['secoes'] = [{**s, 'status': status[s['numero']]} for s in ETP_TIC_SECOES]
        return context


class EtpTicPreviewView(SuperuserRequiredMixin, DetailView):
    model = EtpTic
    template_name = 'licitacoes/etp_preview.html'
    context_object_name = 'etp'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['secoes_render'] = render_etp_sections(self.object)
        return context


class EtpTicConcluirView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        etp = get_object_or_404(EtpTic, pk=pk)
        etp.status = EtpTic.Status.CONCLUIDO
        etp.save(update_fields=['status', 'atualizado_em'])
        messages.success(request, 'ETP TIC concluido.')
        return redirect('licitacoes:etp_preview', pk=pk)


class EtpTicDeleteView(SuperuserRequiredMixin, DeleteView):
    model = EtpTic
    template_name = 'licitacoes/confirm_delete.html'
    success_url = reverse_lazy('licitacoes:etp_list')


class EtpTicExportDocxView(SuperuserRequiredMixin, View):
    def get(self, request, pk):
        etp = get_object_or_404(EtpTic, pk=pk)
        return _docx_response(f'ETP TIC - {etp.nome}', render_etp_sections(etp), f'etp_tic_{slugify(etp.nome) or etp.pk}.docx')


class DfdListView(SuperuserRequiredMixin, ListView):
    model = Dfd
    template_name = 'licitacoes/dfd_list.html'
    context_object_name = 'dfds'


class DfdCreateView(SuperuserRequiredMixin, CreateView):
    model = Dfd
    form_class = DfdCreateForm
    template_name = 'licitacoes/form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo DFD'
        context['voltar_url'] = reverse('licitacoes:dfd_list')
        return context

    def form_valid(self, form):
        self.object = form.save()
        return redirect(f"{reverse('licitacoes:dfd_edit', args=[self.object.pk])}?secao=1")


class DfdEditView(SuperuserRequiredMixin, UpdateView):
    model = Dfd
    form_class = DfdSecaoForm
    template_name = 'licitacoes/dfd_edit.html'
    context_object_name = 'dfd'

    def _secao_numero(self):
        try:
            numero = int(self.request.GET.get('secao') or self.object.secao_atual or 1)
        except (TypeError, ValueError):
            numero = 1
        return numero if numero in DFD_SECOES_MAP else 1

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['section_fields'] = DFD_SECOES_MAP[self._secao_numero()]['campos']
        return kwargs

    def form_valid(self, form):
        dfd = form.save(commit=False)
        secao = self._secao_numero()
        acao = self.request.POST.get('_acao', 'salvar')
        if acao == 'proximo':
            dfd.secao_atual = min(secao + 1, len(DFD_SECOES))
        elif acao == 'anterior':
            dfd.secao_atual = max(secao - 1, 1)
        else:
            dfd.secao_atual = secao
        dfd.save()
        return redirect(f"{reverse('licitacoes:dfd_edit', args=[dfd.pk])}?secao={dfd.secao_atual}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        secao_numero = self._secao_numero()
        status = dfd_status_por_secao(self.object)
        context['secao_numero'] = secao_numero
        context['secao_atual'] = DFD_SECOES_MAP[secao_numero]
        context['secoes'] = [{**s, 'status': status[s['numero']]} for s in DFD_SECOES]
        context['itens_tabela'] = self.object.itens_tabela.order_by('ordem', 'id')
        return context


class DfdPreviewView(SuperuserRequiredMixin, DetailView):
    model = Dfd
    template_name = 'licitacoes/dfd_preview.html'
    context_object_name = 'dfd'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['secoes_render'] = render_dfd_sections(self.object)
        return context


class DfdConcluirView(SuperuserRequiredMixin, View):
    def post(self, request, pk):
        dfd = get_object_or_404(Dfd, pk=pk)
        dfd.status = Dfd.Status.CONCLUIDO
        dfd.save(update_fields=['status', 'atualizado_em'])
        messages.success(request, 'DFD concluido.')
        return redirect('licitacoes:dfd_preview', pk=pk)


class DfdDeleteView(SuperuserRequiredMixin, DeleteView):
    model = Dfd
    template_name = 'licitacoes/confirm_delete.html'
    success_url = reverse_lazy('licitacoes:dfd_list')


class DfdItemTabelaCreateView(SuperuserRequiredMixin, CreateView):
    model = DfdItemTabela
    form_class = DfdItemTabelaForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.dfd = get_object_or_404(Dfd, pk=kwargs['dfd_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.dfd = self.dfd
        self.object.ordem = (self.dfd.itens_tabela.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        self.object.save()
        return redirect(f"{reverse('licitacoes:dfd_edit', args=[self.dfd.pk])}?secao=2#dfd-tabela")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo item da tabela do DFD'
        context['voltar_url'] = f"{reverse('licitacoes:dfd_edit', args=[self.dfd.pk])}?secao=2#dfd-tabela"
        return context


class DfdItemTabelaUpdateView(SuperuserRequiredMixin, UpdateView):
    model = DfdItemTabela
    form_class = DfdItemTabelaForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.dfd = get_object_or_404(Dfd, pk=kwargs['dfd_pk'])
        self.object = get_object_or_404(DfdItemTabela, pk=kwargs['pk'], dfd=self.dfd)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def get_success_url(self):
        return f"{reverse('licitacoes:dfd_edit', args=[self.dfd.pk])}?secao=2#dfd-tabela"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar item da tabela do DFD'
        context['voltar_url'] = self.get_success_url()
        return context


class DfdItemTabelaDeleteView(SuperuserRequiredMixin, DeleteView):
    model = DfdItemTabela
    template_name = 'licitacoes/confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.dfd = get_object_or_404(Dfd, pk=kwargs['dfd_pk'])
        self.object = get_object_or_404(DfdItemTabela, pk=kwargs['pk'], dfd=self.dfd)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def form_valid(self, form):
        self.object.delete()
        for idx, item in enumerate(self.dfd.itens_tabela.order_by('ordem', 'id'), start=1):
            if item.ordem != idx:
                item.ordem = idx
                item.save(update_fields=['ordem'])
        return redirect(f"{reverse('licitacoes:dfd_edit', args=[self.dfd.pk])}?secao=2#dfd-tabela")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir item da tabela do DFD'
        context['voltar_url'] = f"{reverse('licitacoes:dfd_edit', args=[self.dfd.pk])}?secao=2#dfd-tabela"
        return context


class DfdExportDocxView(SuperuserRequiredMixin, View):
    def get(self, request, pk):
        dfd = get_object_or_404(Dfd, pk=pk)
        return _dfd_docx_response(dfd)


class TermoListView(SuperuserRequiredMixin, ListView):
    model = TermoReferencia
    template_name = 'licitacoes/tr_list.html'
    context_object_name = 'termos'


class TermoCreateView(SuperuserRequiredMixin, CreateView):
    model = TermoReferencia
    form_class = TermoReferenciaForm
    template_name = 'licitacoes/form.html'

    def get_success_url(self):
        return reverse('licitacoes:tr_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo TR'
        context['voltar_url'] = reverse('licitacoes:tr_list')
        return context


class TermoUpdateView(SuperuserRequiredMixin, UpdateView):
    model = TermoReferencia
    form_class = TermoReferenciaForm
    template_name = 'licitacoes/form.html'

    def get_success_url(self):
        return reverse('licitacoes:tr_detail', args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar TR'
        context['voltar_url'] = reverse('licitacoes:tr_detail', args=[self.object.pk])
        return context


class TermoDeleteView(SuperuserRequiredMixin, DeleteView):
    model = TermoReferencia
    template_name = 'licitacoes/confirm_delete.html'
    success_url = reverse_lazy('licitacoes:tr_list')


class TermoDetailView(SuperuserRequiredMixin, DetailView):
    model = TermoReferencia
    template_name = 'licitacoes/tr_detail.html'
    context_object_name = 'termo'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tree'] = build_termo_tree(self.object)
        return context


class SessaoCreateView(SuperuserRequiredMixin, CreateView):
    model = SessaoTR
    form_class = SessaoTRForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.termo = get_object_or_404(TermoReferencia, pk=kwargs['termo_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.termo = self.termo
        self.object.ordem = next_ordem_sessao(self.termo)
        self.object.save()
        return redirect('licitacoes:tr_detail', pk=self.termo.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Nova sessao'
        context['voltar_url'] = reverse('licitacoes:tr_detail', args=[self.termo.pk])
        return context


class SessaoUpdateView(SuperuserRequiredMixin, UpdateView):
    model = SessaoTR
    form_class = SessaoTRForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(SessaoTR, pk=kwargs['pk'], termo_id=kwargs['termo_pk'])
        self.termo = self.object.termo
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def get_success_url(self):
        return reverse('licitacoes:tr_detail', args=[self.termo.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar sessao'
        context['voltar_url'] = reverse('licitacoes:tr_detail', args=[self.termo.pk])
        return context


class SessaoDeleteView(SuperuserRequiredMixin, DeleteView):
    model = SessaoTR
    template_name = 'licitacoes/confirm_delete.html'

    def get_queryset(self):
        return SessaoTR.objects.filter(termo_id=self.kwargs['termo_pk'])

    def get_success_url(self):
        termo = self.object.termo
        normalize_sessoes(termo)
        return reverse('licitacoes:tr_detail', args=[termo.pk])


class ItemCreateView(SuperuserRequiredMixin, CreateView):
    model = ItemTR
    form_class = ItemTRForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.sessao = get_object_or_404(SessaoTR, pk=kwargs['sessao_pk'])
        self.parent = None
        if kwargs.get('parent_pk'):
            self.parent = get_object_or_404(ItemTR, pk=kwargs['parent_pk'], sessao__termo=self.sessao.termo)
        self.tipo = request.GET.get('tipo') or ItemTR.Tipo.NUMERICO
        if self.tipo not in ItemTR.Tipo.values:
            self.tipo = ItemTR.Tipo.NUMERICO
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        parent = item_parent_for_tipo(self.parent, self.tipo)
        self.object.sessao = parent.sessao if parent else self.sessao
        self.object.parent = parent
        self.object.tipo = self.tipo
        self.object.ordem = next_ordem_item(self.object.sessao, parent)
        self.object.save()
        return redirect(item_focus_url(self.object))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo item do TR'
        context['ctrl_enter_submit'] = True
        if self.parent:
            context['voltar_url'] = item_focus_url(self.parent)
        else:
            context['voltar_url'] = reverse('licitacoes:tr_detail', args=[self.sessao.termo.pk])
        return context


class ItemUpdateView(SuperuserRequiredMixin, UpdateView):
    model = ItemTR
    form_class = ItemTRForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(ItemTR, pk=kwargs['pk'], sessao__termo__sessoes__id=kwargs['sessao_pk'])
        self.sessao = self.object.sessao
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def form_valid(self, form):
        self.object = form.save()
        return redirect(item_focus_url(self.object))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar item'
        context['ctrl_enter_submit'] = True
        context['voltar_url'] = item_focus_url(self.object)
        return context


class ItemDeleteView(SuperuserRequiredMixin, DeleteView):
    model = ItemTR
    template_name = 'licitacoes/confirm_delete.html'

    def get_queryset(self):
        return ItemTR.objects.filter(sessao__termo__sessoes__id=self.kwargs['sessao_pk'])

    def form_valid(self, form):
        sessao = self.object.sessao
        parent_id = self.object.parent_id
        return_url = item_delete_return_url(self.object)
        self.object.delete()
        normalize_sessoes(sessao.termo)
        normalize_items(sessao, parent_id)
        return redirect(return_url)


class ItemMoveView(SuperuserRequiredMixin, View):
    template_name = 'licitacoes/item_move.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(ItemTR, pk=kwargs['pk'], sessao__termo__sessoes__id=kwargs['sessao_pk'])
        self.termo = self.item.sessao.termo
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = ItemMoveForm(termo=self.termo, item=self.item)
        return _render(request, self.template_name, {'form': form, 'item': self.item, 'termo': self.termo, 'modo': 'mover'})

    def post(self, request, *args, **kwargs):
        form = ItemMoveForm(request.POST, termo=self.termo, item=self.item)
        if form.is_valid():
            target_token = form.cleaned_data['target']
            action = form.cleaned_data['action']
            child_position = form.cleaned_data.get('child_position')
            target = None
            target_sessao = None
            if target_token.startswith('item:'):
                target = get_object_or_404(ItemTR, pk=int(target_token.split(':', 1)[1]), sessao__termo=self.termo)
            else:
                target_sessao = get_object_or_404(SessaoTR, pk=int(target_token.split(':', 1)[1]), termo=self.termo)
                action = 'child'
            try:
                move_item(self.item, target, action, target_sessao=target_sessao, child_position=child_position)
                messages.success(request, 'Item movido e estrutura renumerada.')
                return redirect(item_focus_url(self.item))
            except ValueError as exc:
                form.add_error(None, str(exc))
        return _render(request, self.template_name, {'form': form, 'item': self.item, 'termo': self.termo, 'modo': 'mover'})


class ItemDuplicateView(SuperuserRequiredMixin, View):
    template_name = 'licitacoes/item_move.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(ItemTR, pk=kwargs['pk'], sessao__termo__sessoes__id=kwargs['sessao_pk'])
        self.termo = self.item.sessao.termo
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = ItemMoveForm(termo=self.termo, item=self.item, action_label='Duplicar')
        return _render(request, self.template_name, {'form': form, 'item': self.item, 'termo': self.termo, 'modo': 'duplicar'})

    def post(self, request, *args, **kwargs):
        form = ItemMoveForm(request.POST, termo=self.termo, item=self.item, action_label='Duplicar')
        if form.is_valid():
            target_token = form.cleaned_data['target']
            action = form.cleaned_data['action']
            child_position = form.cleaned_data.get('child_position')
            target = None
            target_sessao = None
            if target_token.startswith('item:'):
                target = get_object_or_404(ItemTR, pk=int(target_token.split(':', 1)[1]), sessao__termo=self.termo)
            else:
                target_sessao = get_object_or_404(SessaoTR, pk=int(target_token.split(':', 1)[1]), termo=self.termo)
                action = 'child'
            try:
                duplicate = duplicate_item(self.item, target, action, target_sessao=target_sessao, child_position=child_position)
                messages.success(request, 'Item duplicado com subitens e estrutura renumerada.')
                return redirect(item_focus_url(duplicate))
            except ValueError as exc:
                form.add_error(None, str(exc))
        return _render(request, self.template_name, {'form': form, 'item': self.item, 'termo': self.termo, 'modo': 'duplicar'})


class TabelaItemCreateView(SuperuserRequiredMixin, CreateView):
    model = TabelaItemLinha
    form_class = TabelaItemLinhaForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_item_tabela_1_1(kwargs['sessao_pk'], kwargs['item_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.item = self.item
        self.object.ordem = (self.item.tabela_linhas.aggregate(max_ordem=Max('ordem'))['max_ordem'] or 0) + 1
        self.object.save()
        return redirect(tabela_item_url(self.item))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Novo item da tabela - Item {item_indice(self.item)}'
        context['voltar_url'] = tabela_item_url(self.item)
        return context


class TabelaItemUpdateView(SuperuserRequiredMixin, UpdateView):
    model = TabelaItemLinha
    form_class = TabelaItemLinhaForm
    template_name = 'licitacoes/form.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_item_tabela_1_1(kwargs['sessao_pk'], kwargs['item_pk'])
        self.object = get_object_or_404(TabelaItemLinha, pk=kwargs['pk'], item=self.item)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def get_success_url(self):
        return tabela_item_url(self.item)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f'Editar item da tabela - Item {item_indice(self.item)}'
        context['voltar_url'] = tabela_item_url(self.item)
        return context


class TabelaItemDeleteView(SuperuserRequiredMixin, DeleteView):
    model = TabelaItemLinha
    template_name = 'licitacoes/confirm_delete.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_item_tabela_1_1(kwargs['sessao_pk'], kwargs['item_pk'])
        self.object = get_object_or_404(TabelaItemLinha, pk=kwargs['pk'], item=self.item)
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        return self.object

    def form_valid(self, form):
        self.object.delete()
        for idx, linha in enumerate(self.item.tabela_linhas.order_by('ordem', 'id'), start=1):
            if linha.ordem != idx:
                linha.ordem = idx
                linha.save(update_fields=['ordem'])
        return redirect(tabela_item_url(self.item))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Excluir item da tabela'
        context['voltar_url'] = tabela_item_url(self.item)
        return context


class TermoExportDocxView(SuperuserRequiredMixin, View):
    def get(self, request, pk):
        termo = get_object_or_404(TermoReferencia, pk=pk)
        from docx import Document
        from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.shared import Cm, Pt, RGBColor

        document = Document()
        normal = document.styles['Normal']
        normal.font.name = 'Verdana'
        normal.font.size = Pt(10)
        section = document.sections[0]
        section.top_margin = Cm(1.8)
        section.bottom_margin = Cm(1.8)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        r = p.add_run(f'TR - {termo.nome}')
        r.bold = True
        r.font.size = Pt(12)

        meta = document.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        meta.add_run('Processo: ').bold = True
        meta.add_run(termo.numero_processo or '-')
        if termo.link:
            link = document.add_paragraph()
            link.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            link.add_run('Link: ').bold = True
            link.add_run(termo.link)

        def add_marked_runs(paragraph, text):
            for segment, is_red in red_mark_segments(text):
                lines = segment.split('\n')
                for idx, line in enumerate(lines):
                    if idx:
                        paragraph.add_run().add_break()
                    if not line:
                        continue
                    run = paragraph.add_run(line)
                    if is_red:
                        run.font.color.rgb = RGBColor(255, 0, 0)

        for bloco in build_termo_tree(termo):
            h = document.add_paragraph()
            h.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            run = h.add_run(f"{bloco['sessao'].ordem}. {bloco['sessao'].titulo}")
            run.bold = True

            rows = bloco['rows']
            if not rows:
                p = document.add_paragraph(f"{bloco['sessao'].ordem}.1. -")
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            for row in rows:
                prefix = row['enum_prefix'] or f"{row['indice']}."
                p = document.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                run_prefix = p.add_run(f'{prefix} ')
                run_prefix.bold = True
                add_marked_runs(p, row['item'].texto or '')

                if row['indice'] == '1.1' and row.get('tabela_linhas'):
                    doc_table = document.add_table(rows=1, cols=6)
                    doc_table.style = 'Table Grid'
                    doc_table.alignment = WD_TABLE_ALIGNMENT.LEFT
                    headers = ['Item', 'Descricao', 'CATMAT/CATSER', 'Siafisico', 'UF', 'Quantidade']
                    for idx, title in enumerate(headers):
                        cell = doc_table.rows[0].cells[idx]
                        paragraph = cell.paragraphs[0]
                        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        header_run = paragraph.add_run(title)
                        header_run.bold = True
                        header_run.font.size = Pt(8)
                        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

                    for linha in row['tabela_linhas']:
                        cells = doc_table.add_row().cells
                        values = [
                            str(linha.ordem),
                            linha.descricao or '-',
                            linha.catmat_catser or '-',
                            linha.siafisico or '-',
                            linha.unidade_fornecimento or '-',
                            quantidade_text(linha.quantidade),
                        ]
                        for idx, value in enumerate(values):
                            if idx == 1:
                                add_marked_runs(cells[idx].paragraphs[0], value)
                            else:
                                cells[idx].text = value
                            cells[idx].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                        cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                        cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                        cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                        cells[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                        cells[5].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            document.add_paragraph('')

        buffer = BytesIO()
        document.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = f'attachment; filename="tr_{slugify(termo.nome) or termo.pk}.docx"'
        return response


def _docx_response(titulo, secoes, filename):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    document = Document()
    normal = document.styles['Normal']
    normal.font.name = 'Verdana'
    normal.font.size = Pt(10)
    section = document.sections[0]
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(titulo)
    r.bold = True
    r.font.size = Pt(12)

    for secao in secoes:
        h = document.add_paragraph()
        h.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        run = h.add_run(f"{secao['numero']}. {secao['titulo']}")
        run.bold = True
        for entrada in secao['entradas'] or [f"{secao['numero']}.1. -"]:
            p = document.add_paragraph(entrada)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        document.add_paragraph('')

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _dfd_docx_response(dfd):
    from docx import Document
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt

    document = Document()
    normal = document.styles['Normal']
    normal.font.name = 'Verdana'
    normal.font.size = Pt(10)
    section = document.sections[0]
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(f'DFD - {dfd.nome}')
    r.bold = True
    r.font.size = Pt(12)

    meta = document.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    meta.add_run('Processo: ').bold = True
    meta.add_run(dfd.numero_processo or '-')
    meta.add_run(' | Status: ').bold = True
    meta.add_run(dfd.get_status_display())

    for secao in render_dfd_sections(dfd):
        h = document.add_paragraph()
        h.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        prefix = f"{secao['numero_documento']}. " if secao.get('numerar') else ''
        run = h.add_run(f"{prefix}{secao['titulo']}")
        run.bold = True

        for entrada in secao['entradas'] or ['-']:
            p = document.add_paragraph(entrada)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        if secao.get('tabela'):
            table = document.add_table(rows=1, cols=6)
            table.style = 'Table Grid'
            headers = ['Item', 'Equipamento', 'CATMAT', 'SIAFISICO', 'Quantidade', 'Descricao']
            for idx, title in enumerate(headers):
                cell = table.rows[0].cells[idx]
                paragraph = cell.paragraphs[0]
                paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                header_run = paragraph.add_run(title)
                header_run.bold = True
                header_run.font.size = Pt(8)
                cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for linha in secao['tabela']:
                cells = table.add_row().cells
                values = [
                    linha.item or str(linha.ordem),
                    linha.equipamento,
                    linha.catmat or '-',
                    linha.siafisico or '-',
                    str(linha.quantidade),
                    linha.descricao or '-',
                ]
                for idx, value in enumerate(values):
                    cells[idx].text = value
                    cells[idx].vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                cells[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        document.add_paragraph('')

    buffer = BytesIO()
    document.save(buffer)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename="dfd_{slugify(dfd.nome) or dfd.pk}.docx"'
    return response


def _render(request, template_name, context):
    from django.shortcuts import render

    return render(request, template_name, context)
