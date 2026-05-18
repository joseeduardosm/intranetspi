from io import BytesIO

from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from .forms import EtpTicCreateForm, EtpTicSecaoForm, ItemMoveForm, ItemTRForm, SessaoTRForm, TermoReferenciaForm
from .models import EtpTic, ItemTR, SessaoTR, TermoReferencia
from .services import (
    ETP_TIC_SECOES,
    ETP_TIC_SECOES_MAP,
    build_item_rows,
    build_termo_tree,
    etp_status_por_secao,
    move_item,
    next_ordem_item,
    next_ordem_sessao,
    normalize_sessoes,
    render_etp_sections,
)


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
        self.object.sessao = self.parent.sessao if self.parent else self.sessao
        self.object.parent = self.parent
        self.object.tipo = self.tipo
        self.object.ordem = next_ordem_item(self.object.sessao, self.parent)
        self.object.save()
        return redirect('licitacoes:tr_detail', pk=self.object.sessao.termo.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Novo item do TR'
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
        return redirect('licitacoes:tr_detail', pk=self.object.sessao.termo.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar item'
        context['voltar_url'] = reverse('licitacoes:tr_detail', args=[self.sessao.termo.pk])
        return context


class ItemDeleteView(SuperuserRequiredMixin, DeleteView):
    model = ItemTR
    template_name = 'licitacoes/confirm_delete.html'

    def get_queryset(self):
        return ItemTR.objects.filter(sessao__termo__sessoes__id=self.kwargs['sessao_pk'])

    def get_success_url(self):
        sessao = self.object.sessao
        parent_id = self.object.parent_id
        termo_pk = sessao.termo.pk
        normalize_sessoes(sessao.termo)
        from .services import normalize_items

        normalize_items(sessao, parent_id)
        return reverse('licitacoes:tr_detail', args=[termo_pk])


class ItemMoveView(SuperuserRequiredMixin, View):
    template_name = 'licitacoes/item_move.html'

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(ItemTR, pk=kwargs['pk'], sessao__termo__sessoes__id=kwargs['sessao_pk'])
        self.termo = self.item.sessao.termo
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        form = ItemMoveForm(termo=self.termo, item=self.item)
        return _render(request, self.template_name, {'form': form, 'item': self.item, 'termo': self.termo})

    def post(self, request, *args, **kwargs):
        form = ItemMoveForm(request.POST, termo=self.termo, item=self.item)
        if form.is_valid():
            target_token = form.cleaned_data['target']
            action = form.cleaned_data['action']
            target = None
            target_sessao = None
            if target_token.startswith('item:'):
                target = get_object_or_404(ItemTR, pk=int(target_token.split(':', 1)[1]), sessao__termo=self.termo)
            else:
                target_sessao = get_object_or_404(SessaoTR, pk=int(target_token.split(':', 1)[1]), termo=self.termo)
                action = 'child'
            try:
                move_item(self.item, target, action, target_sessao=target_sessao)
                messages.success(request, 'Item movido e estrutura renumerada.')
                return redirect('licitacoes:tr_detail', pk=self.termo.pk)
            except ValueError as exc:
                form.add_error(None, str(exc))
        return _render(request, self.template_name, {'form': form, 'item': self.item, 'termo': self.termo})


class TermoExportDocxView(SuperuserRequiredMixin, View):
    def get(self, request, pk):
        termo = get_object_or_404(TermoReferencia, pk=pk)
        secoes = []
        for bloco in build_termo_tree(termo):
            entradas = []
            for row in bloco['rows']:
                prefix = row['enum_prefix'] or f"{row['indice']}."
                entradas.append(f"{prefix} {row['item'].texto}")
            secoes.append({'numero': bloco['sessao'].ordem, 'titulo': bloco['sessao'].titulo, 'descricao': '', 'entradas': entradas})
        return _docx_response(f'TR - {termo.nome}', secoes, f'tr_{slugify(termo.nome) or termo.pk}.docx')


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


def _render(request, template_name, context):
    from django.shortcuts import render

    return render(request, template_name, context)
