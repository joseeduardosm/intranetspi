# Criado por OpenAI Codex em 17/06/2026
# Implementa agenda, CRUDs, solicitações do usuário e análise operacional dos fiscais.

from __future__ import annotations

from datetime import date
from urllib.parse import urlencode
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from acls.mixins import ACLRequiredMixin
from acls.models import RegraAcesso
from acls.utils import obter_nivel_acesso

from .forms import (
    ConfiguracaoReservaGaragemForm,
    ReservaGaragemAnaliseForm,
    ReservaGaragemSolicitacaoForm,
    VagaGaragemForm,
    vagas_disponiveis_no_periodo,
)
from .models import ConfiguracaoReservaGaragem, ReservaGaragem, ReservaGaragemEvento, VagaGaragem
from .services import (
    cancelar_reserva,
    deferir_reserva,
    fiscal_group,
    indeferir_reserva,
    notificar_fiscais_nova_solicitacao,
    registrar_evento,
    reserva_garagem_dashboard_context,
    user_is_fiscal,
)


User = get_user_model()


def _nome_curto(nome: str) -> str:
    """Reduz nomes longos para melhorar tooltip e cartões compactos."""

    partes = [parte for parte in (nome or "").split() if parte]
    return " ".join(partes[:2]) if partes else ""


def _dados_usuario(usuario):
    """Normaliza dados do perfil para tooltip, detalhe e ranking."""

    if not usuario:
        return {
            "nome": "",
            "nome_curto": "",
            "ramal": "",
            "email": "",
            "cargo": "",
            "setor": "",
            "celular": "",
            "whatsapp": "",
            "localizacao": "",
            "foto_url": "",
            "iniciais": "",
        }
    perfil = getattr(usuario, "perfil", None)
    nome = (getattr(perfil, "nome_completo", "") or usuario.get_full_name() or usuario.username).strip()
    iniciais = "".join(parte[0] for parte in nome.split()[:2]).upper() if nome else ""
    return {
        "nome": nome,
        "nome_curto": _nome_curto(nome),
        "ramal": getattr(perfil, "ramal", "") if perfil else "",
        "email": (usuario.email or "").strip(),
        "cargo": getattr(perfil, "cargo", "") if perfil else "",
        "setor": getattr(perfil, "setor", "") if perfil else "",
        "celular": getattr(perfil, "celular", "") if perfil else "",
        "whatsapp": getattr(perfil, "whatsapp_url", "") if perfil else "",
        "localizacao": getattr(perfil, "andar_bloco_display", "") if perfil else "",
        "foto_url": perfil.foto.url if perfil and perfil.foto else "",
        "iniciais": iniciais,
    }


def _nome_usuario_responsavel(user) -> str:
    """Resolve o nome humano usado como responsável automático da reserva."""

    perfil = getattr(user, "perfil", None)
    if perfil and perfil.nome_completo:
        return perfil.nome_completo
    return user.get_full_name() or user.username


def _nivel_usuario(view) -> str | None:
    """Reaproveita o nível ACL já calculado pelo mixin padrão."""

    if hasattr(view, "get_acl_level"):
        return view.get_acl_level()
    return None


def _pode_solicitar(user, acl_level: str | None) -> bool:
    """Usuário solicita vaga quando possui ao menos modificação no módulo."""

    return bool(user and user.is_authenticated and acl_level in {
        RegraAcesso.NIVEL_MODIFICACAO,
        RegraAcesso.NIVEL_CONTROLE_TOTAL,
    })


def _pode_gerenciar_base(acl_level: str | None) -> bool:
    """CRUD de vagas e configuração fica no controle total."""

    return acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL


def _pode_analisar(view) -> bool:
    """Grupo fiscal e controle total acessam a fila de análise."""

    acl_level = _nivel_usuario(view)
    return _pode_gerenciar_base(acl_level) or user_is_fiscal(view.request.user)


def _parse_iso_date(value: str) -> date | None:
    """Converte uma string ISO em data quando o navegador informar um período válido."""

    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _pode_ver_reserva(user, reserva: ReservaGaragem, acl_level: str | None) -> bool:
    """Solicitante vê a própria reserva; fiscais e controle total veem todas."""

    if _pode_gerenciar_base(acl_level) or user_is_fiscal(user):
        return True
    return reserva.solicitante_id == getattr(user, "id", None)


def _pode_editar_reserva(user, reserva: ReservaGaragem, acl_level: str | None) -> bool:
    """Solicitante altera apenas suas reservas pendentes."""

    if _pode_gerenciar_base(acl_level):
        return reserva.status == ReservaGaragem.Status.AGUARDANDO_APROVACAO
    return reserva.solicitante_id == getattr(user, "id", None) and reserva.pode_editar_solicitante


class ReservaGaragemMixin(ACLRequiredMixin):
    """Mixin base do módulo para centralizar slug ACL e contexto auxiliar."""

    recurso_slug = "reserva_garagem"
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        acl_level = _nivel_usuario(self)
        context["reserva_garagem_acl_level"] = acl_level
        context["pode_solicitar_reserva"] = _pode_solicitar(self.request.user, acl_level)
        context["pode_analisar_reservas"] = _pode_analisar(self)
        context["pode_gerenciar_base"] = _pode_gerenciar_base(acl_level)
        return context


class AgendaReservaGaragemView(ReservaGaragemMixin, ListView):
    """Calendário principal com disponibilidade diária consolidada por vaga."""

    model = VagaGaragem
    template_name = "reserva_garagem/agenda.html"
    context_object_name = "vagas"

    def get_queryset(self):
        return VagaGaragem.objects.filter(ativo=True).order_by("nome", "localizacao", "id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vagas = list(context["vagas"])
        reservas = (
            ReservaGaragem.objects.filter(
                status__in=[ReservaGaragem.Status.AGUARDANDO_APROVACAO, ReservaGaragem.Status.DEFERIDA]
            )
            .select_related("solicitante", "vaga")
        )
        ocupacao_por_data_vaga = {}
        for reserva in reservas:
            chave = (reserva.data.isoformat(), reserva.vaga_id)
            ocupacao = ocupacao_por_data_vaga.setdefault(
                chave,
                {
                    "data": reserva.data.isoformat(),
                    "vaga_id": reserva.vaga_id,
                    "occupied": True,
                    # Se qualquer ocupação do dia pertencer ao usuário logado, o círculo recebe anel azul.
                    "is_mine": False,
                },
            )
            if reserva.solicitante_id == getattr(self.request.user, "id", None):
                ocupacao["is_mine"] = True
        vagas_data = [
            {
                "id": vaga.pk,
                "nome_exibicao": vaga.nome_exibicao,
            }
            for vaga in vagas
        ]
        ocupacoes_data = sorted(
            ocupacao_por_data_vaga.values(),
            key=lambda item: (item["data"], item["vaga_id"]),
        )
        context.update(
            {
                "vaga_atual": (self.request.GET.get("vaga") or "").strip(),
                "vagas_data": vagas_data,
                "ocupacoes_data": ocupacoes_data,
                "usuario_logado_nome": _dados_usuario(self.request.user)["nome"] if self.request.user.is_authenticated else "",
                "view_atual": (self.request.GET.get("view") or "month").strip(),
            }
        )
        return context


class ReservaGaragemDashboardView(ReservaGaragemMixin, TemplateView):
    """Dashboard analítico de ocupação da garagem."""

    template_name = "reserva_garagem/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(reserva_garagem_dashboard_context())
        return context


class ReservaListView(ReservaGaragemMixin, ListView):
    """Lista tabular de solicitações com escopo filtrado por perfil do usuário."""

    model = ReservaGaragem
    template_name = "reserva_garagem/reserva_list.html"
    context_object_name = "reservas"
    paginate_by = 20

    def get_queryset(self):
        queryset = ReservaGaragem.objects.select_related("solicitante", "vaga", "fiscal_responsavel")
        acl_level = _nivel_usuario(self)
        if not (_pode_gerenciar_base(acl_level) or user_is_fiscal(self.request.user)):
            queryset = queryset.filter(solicitante=self.request.user)
        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        if status in ReservaGaragem.Status.values:
            queryset = queryset.filter(status=status)
        if query:
            filtros = (
                Q(vaga__nome__icontains=query)
                | Q(vaga__localizacao__icontains=query)
                | Q(placa_veiculo__icontains=query)
                | Q(marca_veiculo__icontains=query)
                | Q(modelo_veiculo__icontains=query)
                | Q(solicitante__username__icontains=query)
                | Q(solicitante__first_name__icontains=query)
            )
            queryset = queryset.filter(filtros)
        return queryset.order_by("-data", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = (self.request.GET.get("q") or "").strip()
        context["status_atual"] = (self.request.GET.get("status") or "").strip()
        context["status_opcoes"] = ReservaGaragem.Status.choices
        return context


class ReservaDetailView(ReservaGaragemMixin, DetailView):
    """Exibe os dados completos da solicitação e o histórico operacional."""

    model = ReservaGaragem
    template_name = "reserva_garagem/reserva_detail.html"
    context_object_name = "reserva"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _pode_ver_reserva(request.user, self.object, _nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ReservaGaragem.objects.select_related(
            "solicitante",
            "solicitante__perfil",
            "vaga",
            "fiscal_responsavel",
            "fiscal_responsavel__perfil",
        ).prefetch_related("eventos__usuario")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["solicitante_payload"] = _dados_usuario(self.object.solicitante)
        context["fiscal_payload"] = _dados_usuario(self.object.fiscal_responsavel)
        context["pode_editar"] = _pode_editar_reserva(self.request.user, self.object, _nivel_usuario(self))
        context["pode_analisar"] = _pode_analisar(self) and self.object.status == ReservaGaragem.Status.AGUARDANDO_APROVACAO
        # Resolve o nome humano do responsável em cada evento para evitar exibir apenas o login no histórico.
        context["eventos_historico"] = [
            {
                "evento": evento,
                "usuario_nome": (_dados_usuario(evento.usuario)["nome"] if evento.usuario else "") or "Sistema",
            }
            for evento in self.object.eventos.all()
        ]
        if self.object.serie_id:
            context["serie_count"] = ReservaGaragem.objects.filter(serie_id=self.object.serie_id).count()
        return context


class ReservaCreateView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Permite ao usuário abrir uma nova solicitação de vaga."""

    model = ReservaGaragem
    form_class = ReservaGaragemSolicitacaoForm
    template_name = "reserva_garagem/reserva_form.html"

    def test_func(self):
        return _pode_solicitar(self.request.user, _nivel_usuario(self))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_initial(self):
        initial = super().get_initial()
        data_param = (self.request.GET.get("data") or "").strip()
        vaga_param = (self.request.GET.get("vaga") or "").strip()
        if data_param:
            try:
                data_base = date.fromisoformat(data_param)
                initial["data_inicial"] = data_base
                initial["data_final"] = data_base
            except ValueError:
                pass
        if vaga_param.isdigit():
            initial["vaga"] = int(vaga_param)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nova solicitação de vaga"
        context["vagas_disponiveis_url"] = reverse("reserva_garagem:vagas_disponiveis")
        return context

    def form_valid(self, form):
        recurrence_dates = form.get_recurrence_dates()
        dados = form.cleaned_data
        responsavel = _nome_usuario_responsavel(self.request.user)
        if recurrence_dates and len(recurrence_dates) > 1:
            serie_id = uuid.uuid4()
            criadas = []
            for occ_date in recurrence_dates:
                criadas.append(
                    ReservaGaragem.objects.create(
                        vaga=dados["vaga"],
                        data=occ_date,
                        responsavel=responsavel,
                        solicitante=self.request.user,
                        marca_veiculo=dados["marca_veiculo"],
                        modelo_veiculo=dados["modelo_veiculo"],
                        cor_veiculo=dados["cor_veiculo"],
                        placa_veiculo=dados["placa_veiculo"],
                        observacoes=dados["observacoes"],
                        serie_id=serie_id,
                    )
                )
            for reserva in criadas:
                registrar_evento(
                    reserva,
                    ReservaGaragemEvento.Acao.CRIACAO,
                    usuario=self.request.user,
                    payload={"data": reserva.data.isoformat(), "serie_id": str(serie_id)},
                )
            queryset = ReservaGaragem.objects.filter(pk__in=[reserva.pk for reserva in criadas]).order_by("data", "id")
            notificar_fiscais_nova_solicitacao(queryset, usuario_responsavel=self.request.user)
            messages.success(self.request, "Série de reservas criada com sucesso.")
            return redirect(criadas[0].get_absolute_url())
        form.instance.solicitante = self.request.user
        form.instance.responsavel = responsavel
        form.instance.data = dados["data_inicial"]
        messages.success(self.request, "Reserva criada com sucesso.")
        response = super().form_valid(form)
        registrar_evento(self.object, ReservaGaragemEvento.Acao.CRIACAO, usuario=self.request.user)
        notificar_fiscais_nova_solicitacao(
            ReservaGaragem.objects.filter(pk=self.object.pk),
            usuario_responsavel=self.request.user,
        )
        return response


class ReservaUpdateView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Permite ao solicitante ajustar a reserva antes da análise."""

    model = ReservaGaragem
    form_class = ReservaGaragemSolicitacaoForm
    template_name = "reserva_garagem/reserva_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def test_func(self):
        return _pode_editar_reserva(self.request.user, self.get_object(), _nivel_usuario(self))

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Editar solicitação"
        context["vagas_disponiveis_url"] = reverse("reserva_garagem:vagas_disponiveis")
        if self.object.serie_id:
            context["serie_count"] = ReservaGaragem.objects.filter(serie_id=self.object.serie_id).count()
        return context

    def form_valid(self, form):
        apply_scope = self.request.POST.get("apply_scope", "single")
        if self.object.serie_id and apply_scope == "all":
            try:
                form.validate_series_update_conflicts(self.object)
            except ValidationError as exc:
                form.add_error(None, exc.message)
                return self.form_invalid(form)
            dados = form.cleaned_data
            ReservaGaragem.objects.filter(serie_id=self.object.serie_id).update(
                vaga=dados["vaga"],
                marca_veiculo=dados["marca_veiculo"],
                modelo_veiculo=dados["modelo_veiculo"],
                cor_veiculo=dados["cor_veiculo"],
                placa_veiculo=dados["placa_veiculo"],
                observacoes=dados["observacoes"],
                atualizado_em=timezone.now(),
            )
            for reserva in ReservaGaragem.objects.filter(serie_id=self.object.serie_id):
                registrar_evento(
                    reserva,
                    ReservaGaragemEvento.Acao.EDICAO,
                    usuario=self.request.user,
                    payload={"apply_scope": "all"},
                )
            messages.success(self.request, "Série de reservas atualizada com sucesso.")
            return redirect(self.get_success_url())
        messages.success(self.request, "Reserva atualizada com sucesso.")
        response = super().form_valid(form)
        registrar_evento(self.object, ReservaGaragemEvento.Acao.EDICAO, usuario=self.request.user, payload={"apply_scope": "single"})
        return response


class ReservaCancelView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Exibe confirmação e executa o cancelamento da solicitação pendente."""

    model = ReservaGaragem
    template_name = "reserva_garagem/reserva_cancel.html"
    context_object_name = "reserva"

    def test_func(self):
        return _pode_editar_reserva(self.request.user, self.get_object(), _nivel_usuario(self))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object.serie_id:
            context["serie_count"] = ReservaGaragem.objects.filter(serie_id=self.object.serie_id).count()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            cancelar_reserva(self.object, usuario=request.user)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect(self.object.get_absolute_url())
        messages.success(request, "Solicitação cancelada com sucesso.")
        return redirect("reserva_garagem:reserva_list")


def vagas_disponiveis_api(request):
    """Retorna as vagas livres para o período informado no formulário de criação/edição."""

    acl_level = obter_nivel_acesso(request.user, "reserva_garagem")
    if not _pode_solicitar(request.user, acl_level):
        raise PermissionDenied

    data_inicial = _parse_iso_date((request.GET.get("data_inicial") or "").strip())
    data_final = _parse_iso_date((request.GET.get("data_final") or "").strip())
    recorrencia = (request.GET.get("recorrencia") or "").strip()

    if not (data_inicial and data_final):
        return JsonResponse({"vagas": [], "mensagem": "", "tem_vagas": False})
    if data_final < data_inicial:
        return JsonResponse(
            {
                "vagas": [],
                "mensagem": "A data final deve ser maior ou igual à data inicial.",
                "tem_vagas": False,
            }
        )

    vagas = list(
        vagas_disponiveis_no_periodo(data_inicial, data_final, recorrencia).values("id", "nome", "localizacao")
    )
    if not vagas:
        mensagem = f"Não há vagas para o período de {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y}"
        return JsonResponse({"vagas": [], "mensagem": mensagem, "tem_vagas": False})

    payload = []
    for vaga in vagas:
        nome_exibicao = vaga["nome"]
        if vaga["localizacao"]:
            nome_exibicao = f"{vaga['nome']} - {vaga['localizacao']}"
        payload.append({"id": vaga["id"], "nome_exibicao": nome_exibicao})
    return JsonResponse({"vagas": payload, "mensagem": "", "tem_vagas": True})


class FilaFiscalListView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Exibe a fila operacional usada pelos fiscais para análise das reservas."""

    model = ReservaGaragem
    template_name = "reserva_garagem/fila_fiscal_list.html"
    context_object_name = "reservas"
    paginate_by = 20

    def test_func(self):
        return _pode_analisar(self)

    def get_queryset(self):
        status = (self.request.GET.get("status") or ReservaGaragem.Status.AGUARDANDO_APROVACAO).strip()
        queryset = ReservaGaragem.objects.select_related("solicitante", "vaga", "fiscal_responsavel")
        if status in ReservaGaragem.Status.values:
            queryset = queryset.filter(status=status)
        if status == ReservaGaragem.Status.AGUARDANDO_APROVACAO:
            queryset = queryset.order_by("data", "id")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_atual"] = (self.request.GET.get("status") or ReservaGaragem.Status.AGUARDANDO_APROVACAO).strip()
        context["status_opcoes"] = ReservaGaragem.Status.choices
        context["grupo_fiscais"] = fiscal_group()
        return context


class FilaFiscalAnaliseView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Tela operacional do fiscal para deferir ou indeferir a reserva."""

    model = ReservaGaragem
    form_class = ReservaGaragemAnaliseForm
    template_name = "reserva_garagem/fila_fiscal_form.html"
    context_object_name = "reserva"

    def test_func(self):
        return _pode_analisar(self)

    def get_success_url(self):
        query = urlencode({"status": self.object.status})
        return f"{reverse('reserva_garagem:fila_fiscal')}?{query}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["solicitante_payload"] = _dados_usuario(self.object.solicitante)
        if self.object.serie_id:
            context["serie_count"] = ReservaGaragem.objects.filter(serie_id=self.object.serie_id).count()
        return context

    def form_valid(self, form):
        try:
            if form.cleaned_data["decisao"] == "DEFERIR":
                deferir_reserva(self.object, fiscal=self.request.user)
                messages.success(self.request, "Solicitação deferida com sucesso.")
            else:
                indeferir_reserva(
                    self.object,
                    fiscal=self.request.user,
                    justificativa=form.cleaned_data["justificativa_indeferimento"],
                )
                messages.success(self.request, "Solicitação indeferida com sucesso.")
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)
        return redirect(self.get_success_url())


class VagaListView(ReservaGaragemMixin, ListView):
    """Lista administrativa das vagas disponíveis."""

    model = VagaGaragem
    template_name = "reserva_garagem/vaga_list.html"
    context_object_name = "vagas"

    def dispatch(self, request, *args, **kwargs):
        if not _pode_gerenciar_base(_nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return VagaGaragem.objects.order_by("nome", "localizacao", "id")


class VagaCreateView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Cria vagas que poderão ser reservadas."""

    model = VagaGaragem
    form_class = VagaGaragemForm
    template_name = "reserva_garagem/vaga_form.html"
    success_url = reverse_lazy("reserva_garagem:vaga_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Vaga cadastrada com sucesso.")
        return super().form_valid(form)


class VagaUpdateView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edita registros das vagas do módulo."""

    model = VagaGaragem
    form_class = VagaGaragemForm
    template_name = "reserva_garagem/vaga_form.html"
    success_url = reverse_lazy("reserva_garagem:vaga_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Vaga atualizada com sucesso.")
        return super().form_valid(form)


class VagaDeleteView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Confirma e remove uma vaga do cadastro administrativo."""

    model = VagaGaragem
    template_name = "reserva_garagem/vaga_confirm_delete.html"
    success_url = reverse_lazy("reserva_garagem:vaga_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Vaga excluída com sucesso.")
        return super().form_valid(form)


class ConfiguracaoUpdateView(ReservaGaragemMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Permite ajustar o grupo operacional dos fiscais do módulo."""

    model = ConfiguracaoReservaGaragem
    form_class = ConfiguracaoReservaGaragemForm
    template_name = "reserva_garagem/configuracao_form.html"
    success_url = reverse_lazy("reserva_garagem:configuracao")

    def get_object(self, queryset=None):
        return ConfiguracaoReservaGaragem.singleton()

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Configuração atualizada com sucesso.")
        return super().form_valid(form)
