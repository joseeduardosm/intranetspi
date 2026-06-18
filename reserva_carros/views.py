# Criado por OpenAI Codex em 12/06/2026
# Implementa calendário, CRUDs, solicitações do usuário e análise operacional dos fiscais.

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from acls.mixins import ACLRequiredMixin
from acls.models import RegraAcesso

from .forms import (
    CarroForm,
    ConfiguracaoReservaCarrosForm,
    MotoristaForm,
    ReservaCarroAnaliseForm,
    ReservaCarroSolicitacaoForm,
)
from .models import Carro, ConfiguracaoReservaCarros, Motorista, ReservaCarro, ReservaCarroEvento
from .services import (
    cancelar_reserva,
    deferir_reserva,
    fiscal_group,
    indeferir_reserva,
    registrar_evento,
    reserva_carros_dashboard_context,
    sync_passageiros,
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


def _nivel_usuario(view) -> str | None:
    """Reaproveita o nível ACL já calculado pelo mixin padrão."""

    if hasattr(view, "get_acl_level"):
        return view.get_acl_level()
    return None


def _pode_solicitar(user, acl_level: str | None) -> bool:
    """Usuário solicita viagens quando possui ao menos leitura no módulo."""

    return bool(user and user.is_authenticated and acl_level in {
        RegraAcesso.NIVEL_LEITURA,
        RegraAcesso.NIVEL_MODIFICACAO,
        RegraAcesso.NIVEL_CONTROLE_TOTAL,
    })


def _pode_gerenciar_base(acl_level: str | None) -> bool:
    """CRUD de carros, motoristas e configuração fica no controle total."""

    return acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL


def _pode_analisar(view) -> bool:
    """Grupo fiscal e controle total acessam a fila de análise."""

    acl_level = _nivel_usuario(view)
    return _pode_gerenciar_base(acl_level) or user_is_fiscal(view.request.user)


def _pode_ver_reserva(user, reserva: ReservaCarro, acl_level: str | None) -> bool:
    """Solicitante vê a própria reserva; fiscais e controle total veem todas."""

    if _pode_gerenciar_base(acl_level) or user_is_fiscal(user):
        return True
    return reserva.solicitante_id == getattr(user, "id", None)


def _pode_editar_reserva(user, reserva: ReservaCarro, acl_level: str | None) -> bool:
    """Solicitante altera apenas suas reservas pendentes."""

    if _pode_gerenciar_base(acl_level):
        return reserva.status == ReservaCarro.Status.AGUARDANDO_APROVACAO
    return reserva.solicitante_id == getattr(user, "id", None) and reserva.pode_editar_solicitante


class ReservaCarrosMixin(ACLRequiredMixin):
    """Mixin base do módulo para centralizar slug ACL e contexto auxiliar."""

    recurso_slug = "reserva_carros"
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        acl_level = _nivel_usuario(self)
        context["reserva_carros_acl_level"] = acl_level
        context["pode_solicitar_viagem"] = _pode_solicitar(self.request.user, acl_level)
        context["pode_analisar_viagens"] = _pode_analisar(self)
        context["pode_gerenciar_base"] = _pode_gerenciar_base(acl_level)
        return context


class AgendaReservaCarrosView(ReservaCarrosMixin, ListView):
    """Calendário principal com reservas pendentes e deferidas visíveis na agenda."""

    model = Carro
    template_name = "reserva_carros/agenda.html"
    context_object_name = "carros"

    def get_queryset(self):
        return Carro.objects.filter(ativo=True).order_by("marca", "modelo", "placa")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        viagens = (
            ReservaCarro.objects.filter(
                status__in=[
                    ReservaCarro.Status.AGUARDANDO_APROVACAO,
                    ReservaCarro.Status.DEFERIDA,
                ]
            )
            .select_related("solicitante", "solicitante__perfil", "carro", "motorista")
            .prefetch_related("passageiros_vinculos__usuario")
        )
        viagens_data = []
        for reserva in viagens:
            dados = _dados_usuario(reserva.solicitante)
            passageiros = [
                vinculo.usuario.get_full_name() or vinculo.usuario.username
                for vinculo in reserva.passageiros_vinculos.select_related("usuario")
            ]
            status_pendente = reserva.status == ReservaCarro.Status.AGUARDANDO_APROVACAO
            viagens_data.append(
                {
                    "id": reserva.pk,
                    "carro_id": reserva.carro_id,
                    "carro_nome": reserva.carro.nome_exibicao if reserva.carro_id else "A definir",
                    "cor": "#9ca3af" if status_pendente else (reserva.carro.cor if reserva.carro_id else "#1f4b99"),
                    "motivo": reserva.motivo_viagem,
                    "status": reserva.status,
                    "status_label": reserva.get_status_display(),
                    "solicitante_nome": dados["nome"],
                    "solicitante_nome_curto": dados["nome_curto"],
                    "solicitante_email": dados["email"],
                    "solicitante_ramal": dados["ramal"],
                    "destino": reserva.destino_endereco,
                    "modo_destino": reserva.get_modo_destino_display(),
                    "passageiros": passageiros,
                    "motorista": reserva.motorista.nome_completo if reserva.motorista_id else "",
                    "inicio": reserva.inicio_bloqueio_em.isoformat() if reserva.inicio_bloqueio_em else reserva.saida_planejada_em.isoformat(),
                    "fim": reserva.fim_bloqueio_em.isoformat() if reserva.fim_bloqueio_em else reserva.retorno_planejado_em.isoformat(),
                    "url": reverse("reserva_carros:solicitacao_detail", kwargs={"pk": reserva.pk}),
                }
            )
        context.update(
            {
                "carro_atual": (self.request.GET.get("carro") or "").strip(),
                "viagens_data": viagens_data,
                "view_atual": (self.request.GET.get("view") or "month").strip(),
            }
        )
        return context


class ReservaCarrosDashboardView(ReservaCarrosMixin, TemplateView):
    """Dashboard analítico reaproveitando o estilo do módulo de espaços."""

    template_name = "reserva_carros/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(reserva_carros_dashboard_context())
        return context


class SolicitacaoListView(ReservaCarrosMixin, ListView):
    """Lista tabular de solicitações com escopo filtrado por perfil do usuário."""

    model = ReservaCarro
    template_name = "reserva_carros/solicitacao_list.html"
    context_object_name = "reservas"
    paginate_by = 20

    def get_queryset(self):
        queryset = ReservaCarro.objects.select_related("solicitante", "carro", "motorista", "fiscal_responsavel")
        acl_level = _nivel_usuario(self)
        if not (_pode_gerenciar_base(acl_level) or user_is_fiscal(self.request.user)):
            queryset = queryset.filter(solicitante=self.request.user)
        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        if status in ReservaCarro.Status.values:
            queryset = queryset.filter(status=status)
        if query:
            filtros = (
                Q(destino_endereco__icontains=query)
                | Q(motivo_viagem__icontains=query)
                | Q(solicitante__username__icontains=query)
                | Q(solicitante__first_name__icontains=query)
                | Q(carro__marca__icontains=query)
                | Q(carro__modelo__icontains=query)
                | Q(carro__placa__icontains=query)
            )
            queryset = queryset.filter(filtros)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = (self.request.GET.get("q") or "").strip()
        context["status_atual"] = (self.request.GET.get("status") or "").strip()
        context["status_opcoes"] = ReservaCarro.Status.choices
        return context


class SolicitacaoDetailView(ReservaCarrosMixin, DetailView):
    """Exibe os dados completos da solicitação e o histórico operacional."""

    model = ReservaCarro
    template_name = "reserva_carros/solicitacao_detail.html"
    context_object_name = "reserva"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _pode_ver_reserva(request.user, self.object, _nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            ReservaCarro.objects.select_related("solicitante", "solicitante__perfil", "carro", "motorista", "fiscal_responsavel")
            .prefetch_related("passageiros_vinculos__usuario", "eventos__usuario")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["solicitante_payload"] = _dados_usuario(self.object.solicitante)
        context["fiscal_payload"] = _dados_usuario(self.object.fiscal_responsavel)
        context["pode_editar"] = _pode_editar_reserva(self.request.user, self.object, _nivel_usuario(self))
        context["pode_analisar"] = _pode_analisar(self) and self.object.status == ReservaCarro.Status.AGUARDANDO_APROVACAO
        # Resolve o nome humano do responsável em cada evento para evitar exibir apenas o login no histórico.
        context["eventos_historico"] = [
            {
                "evento": evento,
                "usuario_nome": (_dados_usuario(evento.usuario)["nome"] if evento.usuario else "") or "Sistema",
            }
            for evento in self.object.eventos.all()
        ]
        return context


class SolicitacaoCreateView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Permite ao usuário abrir uma nova solicitação de viagem."""

    model = ReservaCarro
    form_class = ReservaCarroSolicitacaoForm
    template_name = "reserva_carros/solicitacao_form.html"

    def test_func(self):
        return _pode_solicitar(self.request.user, _nivel_usuario(self))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_initial(self):
        """Pré-preenche a data quando a solicitação nasce a partir do clique no calendário."""

        initial = super().get_initial()
        data_param = (self.request.GET.get("data") or "").strip()
        if not data_param:
            return initial
        try:
            data_base = date.fromisoformat(data_param)
        except ValueError:
            return initial

        # Define horários iniciais neutros para que o formulário já chegue com o dia selecionado.
        initial["saida_planejada_em"] = datetime.combine(data_base, time(hour=9, minute=0))
        initial["retorno_planejado_em"] = datetime.combine(data_base, time(hour=18, minute=0))
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nova solicitação de viagem"
        return context

    def form_valid(self, form):
        form.instance.solicitante = self.request.user
        form.instance.local_saida = ReservaCarro.local_saida_padrao
        response = super().form_valid(form)
        sync_passageiros(self.object, form.cleaned_data.get("passageiros") or [])
        registrar_evento(self.object, ReservaCarroEvento.Acao.CRIACAO, usuario=self.request.user)
        messages.success(self.request, "Solicitação criada com sucesso.")
        return response


class SolicitacaoUpdateView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Permite ao solicitante ajustar a reserva antes da análise."""

    model = ReservaCarro
    form_class = ReservaCarroSolicitacaoForm
    template_name = "reserva_carros/solicitacao_form.html"

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
        return context

    def form_valid(self, form):
        form.instance.local_saida = ReservaCarro.local_saida_padrao
        response = super().form_valid(form)
        sync_passageiros(self.object, form.cleaned_data.get("passageiros") or [])
        registrar_evento(self.object, ReservaCarroEvento.Acao.EDICAO, usuario=self.request.user)
        messages.success(self.request, "Solicitação atualizada com sucesso.")
        return response


class SolicitacaoCancelView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Exibe confirmação e executa o cancelamento da solicitação pendente."""

    model = ReservaCarro
    template_name = "reserva_carros/solicitacao_cancel.html"
    context_object_name = "reserva"

    def test_func(self):
        return _pode_editar_reserva(self.request.user, self.get_object(), _nivel_usuario(self))

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            cancelar_reserva(self.object, usuario=request.user)
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect(self.object.get_absolute_url())
        messages.success(request, "Solicitação cancelada com sucesso.")
        return redirect("reserva_carros:solicitacao_list")


class FilaFiscalListView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Exibe a fila operacional usada pelos fiscais para análise das viagens."""

    model = ReservaCarro
    template_name = "reserva_carros/fila_fiscal_list.html"
    context_object_name = "reservas"
    paginate_by = 20

    def test_func(self):
        return _pode_analisar(self)

    def get_queryset(self):
        status = (self.request.GET.get("status") or ReservaCarro.Status.AGUARDANDO_APROVACAO).strip()
        queryset = ReservaCarro.objects.select_related("solicitante", "carro", "motorista", "fiscal_responsavel")
        if status in ReservaCarro.Status.values:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_atual"] = (self.request.GET.get("status") or ReservaCarro.Status.AGUARDANDO_APROVACAO).strip()
        context["status_opcoes"] = ReservaCarro.Status.choices
        context["grupo_fiscais"] = fiscal_group()
        return context


class FilaFiscalAnaliseView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Tela operacional do fiscal para deferir ou indeferir a reserva."""

    model = ReservaCarro
    form_class = ReservaCarroAnaliseForm
    template_name = "reserva_carros/fila_fiscal_form.html"
    context_object_name = "reserva"

    def test_func(self):
        return _pode_analisar(self)

    def get_success_url(self):
        query = urlencode({"status": self.object.status})
        return f"{reverse('reserva_carros:fila_fiscal')}?{query}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["solicitante_payload"] = _dados_usuario(self.object.solicitante)
        return context

    def form_valid(self, form):
        try:
            if form.cleaned_data["decisao"] == "DEFERIR":
                deferir_reserva(
                    self.object,
                    fiscal=self.request.user,
                    carro=form.cleaned_data["carro"],
                    motorista=form.cleaned_data["motorista"],
                    deslocamento_ida_minutos=form.cleaned_data["deslocamento_ida_minutos"],
                    deslocamento_retorno_minutos=form.cleaned_data["deslocamento_retorno_minutos"],
                )
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


class CarroListView(ReservaCarrosMixin, ListView):
    """Lista administrativa da frota disponível."""

    model = Carro
    template_name = "reserva_carros/carro_list.html"
    context_object_name = "carros"

    def dispatch(self, request, *args, **kwargs):
        if not _pode_gerenciar_base(_nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Carro.objects.order_by("marca", "modelo", "placa")


class CarroCreateView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Cria veículos que poderão ser vinculados às viagens deferidas."""

    model = Carro
    form_class = CarroForm
    template_name = "reserva_carros/carro_form.html"
    success_url = reverse_lazy("reserva_carros:carro_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Carro cadastrado com sucesso.")
        return super().form_valid(form)


class CarroUpdateView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edita registros da frota do módulo."""

    model = Carro
    form_class = CarroForm
    template_name = "reserva_carros/carro_form.html"
    success_url = reverse_lazy("reserva_carros:carro_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Carro atualizado com sucesso.")
        return super().form_valid(form)


class CarroDeleteView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Confirma e remove um carro do cadastro administrativo."""

    model = Carro
    template_name = "reserva_carros/carro_confirm_delete.html"
    success_url = reverse_lazy("reserva_carros:carro_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Carro excluído com sucesso.")
        return super().form_valid(form)


class MotoristaListView(ReservaCarrosMixin, ListView):
    """Lista administrativa dos motoristas disponíveis."""

    model = Motorista
    template_name = "reserva_carros/motorista_list.html"
    context_object_name = "motoristas"

    def dispatch(self, request, *args, **kwargs):
        if not _pode_gerenciar_base(_nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Motorista.objects.order_by("nome_completo")


class MotoristaCreateView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Cria motoristas próprios do módulo."""

    model = Motorista
    form_class = MotoristaForm
    template_name = "reserva_carros/motorista_form.html"
    success_url = reverse_lazy("reserva_carros:motorista_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Motorista cadastrado com sucesso.")
        return super().form_valid(form)


class MotoristaUpdateView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edita motoristas do cadastro próprio do módulo."""

    model = Motorista
    form_class = MotoristaForm
    template_name = "reserva_carros/motorista_form.html"
    success_url = reverse_lazy("reserva_carros:motorista_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Motorista atualizado com sucesso.")
        return super().form_valid(form)


class MotoristaDeleteView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Confirma e remove um motorista do cadastro administrativo."""

    model = Motorista
    template_name = "reserva_carros/motorista_confirm_delete.html"
    success_url = reverse_lazy("reserva_carros:motorista_list")

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Motorista excluído com sucesso.")
        return super().form_valid(form)


class ConfiguracaoUpdateView(ReservaCarrosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Permite ajustar o grupo operacional dos fiscais do módulo."""

    model = ConfiguracaoReservaCarros
    form_class = ConfiguracaoReservaCarrosForm
    template_name = "reserva_carros/configuracao_form.html"
    success_url = reverse_lazy("reserva_carros:configuracao")

    def get_object(self, queryset=None):
        return ConfiguracaoReservaCarros.singleton()

    def test_func(self):
        return _pode_gerenciar_base(_nivel_usuario(self))

    def form_valid(self, form):
        messages.success(self.request, "Configuração atualizada com sucesso.")
        return super().form_valid(form)
