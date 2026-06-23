"""Views do módulo de reserva de espaços com fluxo fiscal."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from io import BytesIO
from urllib.parse import urlencode
import uuid

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from acls.mixins import ACLRequiredMixin, acl_required
from acls.models import RegraAcesso

from .forms import (
    ConfiguracaoReservaEspacosForm,
    ObjetoReservavelForm,
    ReservaRecursoAnaliseForm,
    ReservaRecursoForm,
)
from .models import ConfiguracaoReservaEspacos, ObjetoReservavel, ReservaRecurso, ReservaRecursoEvento
from .services import (
    cancelar_reserva_com_escopo,
    deferir_reserva,
    fiscal_group,
    indeferir_reserva,
    notificar_fiscais_nova_solicitacao,
    registrar_evento,
    reserva_espacos_dashboard_context,
    user_is_fiscal,
)


User = get_user_model()


def _nome_curto(nome: str) -> str:
    """Reduz nomes longos para dois termos em áreas de alta densidade visual."""

    partes = [parte for parte in (nome or "").split() if parte]
    return " ".join(partes[:2]) if partes else ""


def _dados_usuario(usuario):
    """Normaliza dados do perfil para tooltip, detalhe e dashboard."""

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
            "perfil_pk": "",
        }
    perfil = getattr(usuario, "perfil", None)
    nome = ""
    if perfil and perfil.nome_completo:
        nome = perfil.nome_completo
    else:
        nome = usuario.get_full_name() or usuario.username
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
        "perfil_pk": getattr(perfil, "pk", "") if perfil else "",
    }


def _nome_usuario_responsavel(user) -> str:
    """Resolve o nome humano usado como responsável automático da reserva."""

    perfil = getattr(user, "perfil", None)
    if perfil and perfil.nome_completo:
        return perfil.nome_completo
    return user.get_full_name() or user.username


def _nivel_usuario(view) -> str | None:
    """Reaproveita o nível de ACL já calculado nas views com o mixin padrão."""

    if hasattr(view, "get_acl_level"):
        return view.get_acl_level()
    return None


def _pode_criar_reserva(user, acl_level: str | None) -> bool:
    """Usuário pode criar reserva quando tem modificação ou controle total."""

    if not getattr(user, "is_authenticated", False):
        return False
    return acl_level in {RegraAcesso.NIVEL_MODIFICACAO, RegraAcesso.NIVEL_CONTROLE_TOTAL}


def _pode_analisar(view) -> bool:
    """Somente o grupo fiscal e admins do sistema acessam as áreas restritas."""

    return user_is_fiscal(view.request.user)


def _pode_ver_reserva(user, reserva: ReservaRecurso, acl_level: str | None) -> bool:
    """Solicitante vê a própria reserva; fiscais e admins veem todas."""

    if user_is_fiscal(user) or acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL:
        return True
    return reserva.criado_por_id == getattr(user, "id", None)


def _pode_gerenciar_objeto(user, objeto: ObjetoReservavel, acl_level: str | None) -> bool:
    """O cadastro de objetos segue o mesmo escopo operacional dos fiscais."""

    return user_is_fiscal(user) or acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL


def _pode_gerenciar_reserva(user, reserva: ReservaRecurso, acl_level: str | None) -> bool:
    """Solicitante altera apenas o que criou enquanto estiver pendente."""

    if user_is_fiscal(user) or acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL:
        return reserva.status == ReservaRecurso.Status.AGUARDANDO_APROVACAO
    return reserva.criado_por_id == getattr(user, "id", None) and reserva.pode_editar_solicitante


def _pode_cancelar_reserva(user, reserva: ReservaRecurso, acl_level: str | None) -> bool:
    """Cancelamento alcança reservas ativas do próprio usuário ou qualquer reserva para fiscal/admin."""

    if reserva.status not in {
        ReservaRecurso.Status.AGUARDANDO_APROVACAO,
        ReservaRecurso.Status.DEFERIDA,
    }:
        return False
    if user_is_fiscal(user) or acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL:
        return True
    return reserva.criado_por_id == getattr(user, "id", None)


def _parse_iso_date(value: str) -> date | None:
    """Converte uma string ISO em data quando o navegador informar um período válido."""

    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _escopo_evento_legivel(payload: dict) -> str:
    """Traduz o escopo técnico do evento para um texto amigável no histórico."""

    apply_scope = (payload or {}).get("apply_scope") or ""
    data_inicial = _parse_iso_date((payload or {}).get("data_inicial") or "")
    data_final = _parse_iso_date((payload or {}).get("data_final") or "")
    if apply_scope == "all":
        return "Toda a série"
    if apply_scope == "range" and data_inicial and data_final:
        return f"Período de {data_inicial:%d/%m/%Y} a {data_final:%d/%m/%Y}"
    if apply_scope == "single":
        return "Somente esta ocorrência"
    if (payload or {}).get("serie_id"):
        return "Série criada"
    return ""


def _origem_evento_legivel(payload: dict, evento: ReservaRecursoEvento, reserva: ReservaRecurso) -> str:
    """Identifica se a ação veio do fluxo do usuário, do fluxo fiscal ou da pré-reserva."""

    origem = (payload or {}).get("origem") or ""
    if origem == "predefinida_fiscal":
        return "Pré-reserva fiscal"
    if origem == "fluxo_fiscal":
        return "Fluxo fiscal"
    if origem == "fluxo_usuario":
        return "Fluxo do usuário"
    if evento.acao in {ReservaRecursoEvento.Acao.DEFERIMENTO, ReservaRecursoEvento.Acao.INDEFERIMENTO}:
        return "Fluxo fiscal"
    if evento.usuario_id and evento.usuario_id == reserva.criado_por_id:
        return "Fluxo do usuário"
    if evento.usuario_id:
        return "Fluxo fiscal"
    return "Sistema"


class ReservasRecursosMixin(ACLRequiredMixin):
    """Mixin base do módulo com slug fixo e contexto de permissões auxiliares."""

    recurso_slug = "reserva_espacos"
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        acl_level = _nivel_usuario(self)
        context["reservas_acl_level"] = acl_level
        context["pode_criar_reserva"] = _pode_criar_reserva(self.request.user, acl_level)
        context["pode_gerenciar_objetos"] = _pode_gerenciar_objeto(self.request.user, None, acl_level)
        context["pode_analisar_reservas"] = _pode_analisar(self)
        return context


class AgendaReservaView(ReservasRecursosMixin, ListView):
    """Tela principal da agenda com dados serializados para o calendário multi-view."""

    model = ObjetoReservavel
    template_name = "reserva_espacos/agenda.html"
    context_object_name = "objetos"

    def get_queryset(self):
        return ObjetoReservavel.objects.filter(ativo=True).order_by("nome")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservas = ReservaRecurso.objects.select_related("objeto", "criado_por", "criado_por__perfil")
        reservas = reservas.exclude(status__in=[ReservaRecurso.Status.CANCELADA, ReservaRecurso.Status.INDEFERIDA])
        reservas_data = []
        for reserva in reservas:
            dados = _dados_usuario(reserva.criado_por)
            status_css = "pending" if reserva.status == ReservaRecurso.Status.AGUARDANDO_APROVACAO else "approved"
            pode_abrir = _pode_ver_reserva(self.request.user, reserva, _nivel_usuario(self))
            reservas_data.append(
                {
                    "id": reserva.pk,
                    "objeto_id": reserva.objeto_id,
                    "objeto_nome": reserva.objeto.nome,
                    "objeto_localizacao": reserva.objeto.localizacao,
                    "cor": "#6c757d" if status_css == "pending" else reserva.objeto.cor,
                    "titulo": reserva.titulo,
                    "responsavel": reserva.responsavel,
                    "observacoes": reserva.observacoes,
                    "inicio": datetime.combine(reserva.data, reserva.hora_inicio).isoformat(),
                    "fim": datetime.combine(reserva.data, reserva.hora_fim).isoformat(),
                    "criado_por_nome": dados["nome"],
                    "criado_por_nome_curto": dados["nome_curto"],
                    "criado_por_ramal": dados["ramal"],
                    "criado_por_email": dados["email"],
                    "status": reserva.status,
                    "status_label": reserva.get_status_display(),
                    "status_css": status_css,
                    "url": reverse("reserva_espacos:reserva_detail", kwargs={"pk": reserva.pk}) if pode_abrir else "",
                }
            )
        context.update(
            {
                "objeto_atual": (self.request.GET.get("objeto") or "").strip(),
                "reservas_data": reservas_data,
                "view_atual": (self.request.GET.get("view") or "month").strip(),
            }
        )
        return context


class ObjetoListView(ReservasRecursosMixin, ListView):
    """Lista objetos reserváveis cadastrados no módulo."""

    model = ObjetoReservavel
    template_name = "reserva_espacos/objeto_list.html"
    context_object_name = "objetos"

    def dispatch(self, request, *args, **kwargs):
        if not _pode_analisar(self):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ObjetoReservavel.objects.order_by("nome")


class ObjetoCreateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Cria objetos; sem categorias, o cadastro fica no escopo fiscal/admin."""

    model = ObjetoReservavel
    form_class = ObjetoReservavelForm
    template_name = "reserva_espacos/objeto_form.html"
    success_url = reverse_lazy("reserva_espacos:objeto_list")

    def test_func(self):
        return _pode_analisar(self)

    def form_valid(self, form):
        messages.success(self.request, "Objeto cadastrado com sucesso.")
        return super().form_valid(form)


class ObjetoUpdateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edita objetos existentes no escopo operacional do módulo."""

    model = ObjetoReservavel
    form_class = ObjetoReservavelForm
    template_name = "reserva_espacos/objeto_form.html"
    success_url = reverse_lazy("reserva_espacos:objeto_list")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _pode_gerenciar_objeto(request.user, self.object, _nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        return _pode_analisar(self)

    def form_valid(self, form):
        messages.success(self.request, "Objeto atualizado com sucesso.")
        return super().form_valid(form)


class ObjetoDeleteView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Exclui objetos somente no escopo fiscal/admin."""

    model = ObjetoReservavel
    template_name = "reserva_espacos/objeto_confirm_delete.html"
    success_url = reverse_lazy("reserva_espacos:objeto_list")

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _pode_gerenciar_objeto(request.user, self.object, _nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def test_func(self):
        return _pode_analisar(self)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reservas_relacionadas"] = self.object.reservas.count()
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Objeto excluído com sucesso.")
        return super().delete(request, *args, **kwargs)


class ReservaListView(ReservasRecursosMixin, ListView):
    """Lista tabular restrita ao time fiscal com filtro textual e por status."""

    model = ReservaRecurso
    template_name = "reserva_espacos/reserva_list.html"
    context_object_name = "reservas"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not _pode_analisar(self):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = ReservaRecurso.objects.select_related("objeto", "criado_por", "fiscal_responsavel").all()
        query = (self.request.GET.get("q") or "").strip()
        status = (self.request.GET.get("status") or "").strip()
        if status in ReservaRecurso.Status.values:
            queryset = queryset.filter(status=status)
        if query:
            filtros = (
                Q(titulo__icontains=query)
                | Q(responsavel__icontains=query)
                | Q(objeto__nome__icontains=query)
                | Q(objeto__localizacao__icontains=query)
                | Q(criado_por__username__icontains=query)
                | Q(criado_por__first_name__icontains=query)
            )
            for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    filtros |= Q(data=datetime.strptime(query, formato).date())
                    break
                except ValueError:
                    continue
            queryset = queryset.filter(filtros)
        return queryset.order_by("-data", "hora_inicio", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = (self.request.GET.get("q") or "").strip()
        context["status_atual"] = (self.request.GET.get("status") or "").strip()
        context["status_opcoes"] = ReservaRecurso.Status.choices
        return context


class MinhasReservasView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Lista apenas as reservas do usuário logado com filtros rápidos por status."""

    model = ReservaRecurso
    template_name = "reserva_espacos/minhas_reservas.html"
    context_object_name = "reservas"
    paginate_by = 20

    def test_func(self):
        return _pode_criar_reserva(self.request.user, _nivel_usuario(self))

    def get_queryset(self):
        queryset = ReservaRecurso.objects.select_related("objeto", "fiscal_responsavel").filter(
            criado_por=self.request.user
        )
        status = (self.request.GET.get("status") or "").strip()
        if status in ReservaRecurso.Status.values:
            queryset = queryset.filter(status=status)
        return queryset.order_by("-data", "hora_inicio", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_atual"] = (self.request.GET.get("status") or "").strip()
        context["status_filtros"] = [
            ("", "Todas"),
            (ReservaRecurso.Status.AGUARDANDO_APROVACAO, "Aguardando"),
            (ReservaRecurso.Status.DEFERIDA, "Deferidas"),
            (ReservaRecurso.Status.INDEFERIDA, "Indeferidas"),
            (ReservaRecurso.Status.CANCELADA, "Canceladas"),
        ]
        return context


class ReservaDetailView(ReservasRecursosMixin, DetailView):
    """Mostra todos os dados da reserva em página dedicada."""

    model = ReservaRecurso
    template_name = "reserva_espacos/reserva_detail.html"
    context_object_name = "reserva"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _pode_ver_reserva(request.user, self.object, _nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return ReservaRecurso.objects.select_related(
            "criado_por",
            "criado_por__perfil",
            "objeto",
            "fiscal_responsavel",
            "fiscal_responsavel__perfil",
        ).prefetch_related("eventos__usuario")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dados = _dados_usuario(self.object.criado_por)
        context["criador"] = dados
        context["fiscal_payload"] = _dados_usuario(self.object.fiscal_responsavel)
        context["pode_editar"] = _pode_gerenciar_reserva(self.request.user, self.object, _nivel_usuario(self))
        context["pode_cancelar"] = _pode_cancelar_reserva(self.request.user, self.object, _nivel_usuario(self))
        context["pode_analisar"] = _pode_analisar(self) and self.object.status == ReservaRecurso.Status.AGUARDANDO_APROVACAO
        context["eventos_historico"] = [
            {
                "evento": evento,
                "usuario_nome": (_dados_usuario(evento.usuario)["nome"] if evento.usuario else "") or "Sistema",
                "escopo_label": _escopo_evento_legivel(evento.payload or {}),
                "origem_label": _origem_evento_legivel(evento.payload or {}, evento, self.object),
                "motivo_cancelamento": (evento.payload or {}).get("motivo_cancelamento") or "",
                "justificativa": (evento.payload or {}).get("justificativa") or "",
            }
            for evento in self.object.eventos.all()
        ]
        if self.object.serie_id:
            context["serie_count"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).count()
        return context


class ReservaCreateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Cria reservas simples ou recorrentes conforme a seleção do formulário."""

    model = ReservaRecurso
    form_class = ReservaRecursoForm
    template_name = "reserva_espacos/reserva_form.html"
    success_url = reverse_lazy("reserva_espacos:reserva_list")

    def test_func(self):
        return _pode_criar_reserva(self.request.user, _nivel_usuario(self))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        data_param = self.request.GET.get("data")
        objeto_param = self.request.GET.get("objeto")
        if data_param:
            try:
                initial["data"] = date.fromisoformat(data_param)
            except ValueError:
                pass
        if objeto_param and objeto_param.isdigit():
            initial["objeto"] = int(objeto_param)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Nova reserva"
        context["data_selecionada"] = self.request.GET.get("data") or ""
        context["is_create_mode"] = True
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
                    ReservaRecurso.objects.create(
                        objeto=dados["objeto"],
                        data=occ_date,
                        hora_inicio=dados["hora_inicio"],
                        hora_fim=dados["hora_fim"],
                        titulo=dados["titulo"],
                        responsavel=responsavel,
                        observacoes=dados["observacoes"],
                        criado_por=self.request.user,
                        serie_id=serie_id,
                    )
                )
            for reserva in criadas:
                registrar_evento(
                    reserva,
                    ReservaRecursoEvento.Acao.CRIACAO,
                    usuario=self.request.user,
                    payload={"data": reserva.data.isoformat(), "serie_id": str(serie_id)},
                )
            queryset = ReservaRecurso.objects.filter(pk__in=[reserva.pk for reserva in criadas]).order_by("data", "hora_inicio", "id")
            notificar_fiscais_nova_solicitacao(queryset, usuario_responsavel=self.request.user)
            messages.success(self.request, "Série de reservas criada com sucesso.")
            return redirect(criadas[0].get_absolute_url())
        form.instance.criado_por = self.request.user
        form.instance.responsavel = responsavel
        messages.success(self.request, "Reserva criada com sucesso.")
        response = super().form_valid(form)
        registrar_evento(self.object, ReservaRecursoEvento.Acao.CRIACAO, usuario=self.request.user)
        notificar_fiscais_nova_solicitacao(
            ReservaRecurso.objects.filter(pk=self.object.pk),
            usuario_responsavel=self.request.user,
        )
        return response


class ReservaPredefinidaFiscalCreateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Permite ao time fiscal bloquear salas previamente definidas sem passar pela fila."""

    model = ReservaRecurso
    form_class = ReservaRecursoForm
    template_name = "reserva_espacos/reserva_form.html"

    def test_func(self):
        return _pode_analisar(self)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        kwargs["modo_fiscal"] = True
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        data_param = self.request.GET.get("data")
        objeto_param = self.request.GET.get("objeto")
        if data_param:
            try:
                initial["data"] = date.fromisoformat(data_param)
            except ValueError:
                pass
        if objeto_param and objeto_param.isdigit():
            initial["objeto"] = int(objeto_param)
        initial["responsavel"] = _nome_usuario_responsavel(self.request.user)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Nova pré-reserva"
        context["modo_fiscal_predefinido"] = True
        context["is_create_mode"] = True
        return context

    def form_valid(self, form):
        recurrence_dates = form.get_recurrence_dates()
        dados = form.cleaned_data
        solicitante = form.usuario_responsavel_resolvido or self.request.user
        responsavel = dados["responsavel"]
        fiscal = self.request.user

        if recurrence_dates and len(recurrence_dates) > 1:
            serie_id = uuid.uuid4()
            criadas = []
            for occ_date in recurrence_dates:
                reserva = ReservaRecurso.objects.create(
                    objeto=dados["objeto"],
                    data=occ_date,
                    hora_inicio=dados["hora_inicio"],
                    hora_fim=dados["hora_fim"],
                    titulo=dados["titulo"],
                    responsavel=responsavel,
                    observacoes=dados["observacoes"],
                    criado_por=solicitante,
                    status=ReservaRecurso.Status.DEFERIDA,
                    fiscal_responsavel=fiscal,
                    serie_id=serie_id,
                )
                criadas.append(reserva)
                registrar_evento(
                    reserva,
                    ReservaRecursoEvento.Acao.CRIACAO,
                    usuario=fiscal,
                    payload={"origem": "predefinida_fiscal", "data": reserva.data.isoformat(), "serie_id": str(serie_id)},
                )
                registrar_evento(
                    reserva,
                    ReservaRecursoEvento.Acao.DEFERIMENTO,
                    usuario=fiscal,
                    payload={"origem": "predefinida_fiscal", "serie_id": str(serie_id)},
                )
            messages.success(self.request, "Série de pré-reservas criada com sucesso.")
            return redirect(criadas[0].get_absolute_url())

        form.instance.criado_por = solicitante
        form.instance.responsavel = responsavel
        form.instance.status = ReservaRecurso.Status.DEFERIDA
        form.instance.fiscal_responsavel = fiscal
        messages.success(self.request, "Pré-reserva criada com sucesso.")
        response = super().form_valid(form)
        registrar_evento(
            self.object,
            ReservaRecursoEvento.Acao.CRIACAO,
            usuario=fiscal,
            payload={"origem": "predefinida_fiscal"},
        )
        registrar_evento(
            self.object,
            ReservaRecursoEvento.Acao.DEFERIMENTO,
            usuario=fiscal,
            payload={"origem": "predefinida_fiscal"},
        )
        return response


class ReservaUpdateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edita uma reserva ou a série inteira quando o usuário tem essa autorização."""

    model = ReservaRecurso
    form_class = ReservaRecursoForm
    template_name = "reserva_espacos/reserva_form.html"

    def test_func(self):
        return _pode_gerenciar_reserva(self.request.user, self.get_object(), _nivel_usuario(self))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo_pagina"] = "Editar reserva"
        context["is_create_mode"] = False
        if self.object.serie_id:
            context["serie_count"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).count()
        return context

    def form_valid(self, form):
        apply_scope = self.request.POST.get("apply_scope", "single")
        if form.is_recurring_series() and apply_scope == "all":
            try:
                form.validate_series_update_conflicts(self.object)
            except ValidationError as exc:
                form.add_error(None, exc.message)
                return self.form_invalid(form)
            dados = form.cleaned_data
            ReservaRecurso.objects.filter(serie_id=self.object.serie_id).update(
                objeto=dados["objeto"],
                hora_inicio=dados["hora_inicio"],
                hora_fim=dados["hora_fim"],
                titulo=dados["titulo"],
                responsavel=dados["responsavel"],
                observacoes=dados["observacoes"],
                atualizado_em=timezone.now(),
            )
            for reserva in ReservaRecurso.objects.filter(serie_id=self.object.serie_id):
                registrar_evento(
                    reserva,
                    ReservaRecursoEvento.Acao.EDICAO,
                    usuario=self.request.user,
                    payload={"apply_scope": "all"},
                )
            messages.success(self.request, "Série de reservas atualizada com sucesso.")
            return redirect(self.get_success_url())
        messages.success(self.request, "Reserva atualizada com sucesso.")
        response = super().form_valid(form)
        registrar_evento(self.object, ReservaRecursoEvento.Acao.EDICAO, usuario=self.request.user, payload={"apply_scope": "single"})
        return response


class ReservaCancelView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Exibe confirmação e executa o cancelamento da solicitação ativa."""

    model = ReservaRecurso
    template_name = "reserva_espacos/reserva_cancel.html"
    context_object_name = "reserva"

    def test_func(self):
        return _pode_cancelar_reserva(self.request.user, self.get_object(), _nivel_usuario(self))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object.serie_id:
            context["serie_count"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).count()
            context["serie_primeira_data"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).order_by("data").first().data
            context["serie_ultima_data"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).order_by("-data").first().data
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        apply_scope = (request.POST.get("apply_scope") or "single").strip()
        data_inicial = _parse_iso_date((request.POST.get("cancel_data_inicial") or "").strip())
        data_final = _parse_iso_date((request.POST.get("cancel_data_final") or "").strip())
        motivo_cancelamento = (request.POST.get("motivo_cancelamento") or "").strip()
        try:
            cancelar_reserva_com_escopo(
                self.object,
                usuario=request.user,
                apply_scope=apply_scope,
                data_inicial=data_inicial,
                data_final=data_final,
                motivo_cancelamento=motivo_cancelamento,
            )
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect(self.object.get_absolute_url())
        messages.success(request, "Solicitação cancelada com sucesso.")
        if user_is_fiscal(request.user):
            return redirect("reserva_espacos:reserva_list")
        return redirect("reserva_espacos:minhas_reservas")


class FilaFiscalListView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Exibe a fila operacional usada pelos fiscais para análise das reservas."""

    model = ReservaRecurso
    template_name = "reserva_espacos/fila_fiscal_list.html"
    context_object_name = "reservas"
    paginate_by = 20

    def test_func(self):
        return _pode_analisar(self)

    def get_queryset(self):
        status = (self.request.GET.get("status") or ReservaRecurso.Status.AGUARDANDO_APROVACAO).strip()
        queryset = ReservaRecurso.objects.select_related("criado_por", "objeto", "fiscal_responsavel")
        if status in ReservaRecurso.Status.values:
            queryset = queryset.filter(status=status)
        if status == ReservaRecurso.Status.AGUARDANDO_APROVACAO:
            queryset = queryset.order_by("data", "hora_inicio", "id")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_atual"] = (self.request.GET.get("status") or ReservaRecurso.Status.AGUARDANDO_APROVACAO).strip()
        context["status_opcoes"] = ReservaRecurso.Status.choices
        context["grupo_fiscais"] = fiscal_group()
        return context


class FilaFiscalAnaliseView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Tela operacional do fiscal para deferir ou indeferir a reserva."""

    model = ReservaRecurso
    form_class = ReservaRecursoAnaliseForm
    template_name = "reserva_espacos/fila_fiscal_form.html"
    context_object_name = "reserva"

    def test_func(self):
        return _pode_analisar(self)

    def get_success_url(self):
        query = urlencode({"status": self.object.status})
        return f"{reverse('reserva_espacos:fila_fiscal')}?{query}"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["criador"] = _dados_usuario(self.object.criado_por)
        context["fiscal_payload"] = _dados_usuario(self.object.fiscal_responsavel)
        context["reserva_ja_decidida"] = self.object.status != ReservaRecurso.Status.AGUARDANDO_APROVACAO
        if self.object.serie_id:
            context["serie_count"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).count()
        return context

    def form_valid(self, form):
        if self.object.status != ReservaRecurso.Status.AGUARDANDO_APROVACAO:
            messages.info(
                self.request,
                f"Esta solicitação já foi {self.object.get_status_display().lower()} e não pode ser analisada novamente.",
            )
            return redirect(self.object.get_absolute_url())
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


class ReservaDashboardView(ReservasRecursosMixin, TemplateView):
    """Dashboard analítico adaptado para o fluxo fiscal do módulo."""

    template_name = "reserva_espacos/dashboard.html"

    def dispatch(self, request, *args, **kwargs):
        if not _pode_analisar(self):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(reserva_espacos_dashboard_context())

        ranking_raw = list(
            ReservaRecurso.objects.filter(criado_por__isnull=False)
            .values("criado_por_id")
            .annotate(total=Count("id"))
            .order_by("-total", "criado_por_id")[:15]
        )
        usuarios = User.objects.filter(id__in=[row["criado_por_id"] for row in ranking_raw]).select_related("perfil")
        usuarios_por_id = {usuario.id: usuario for usuario in usuarios}
        ranking_pessoas = []
        for row in ranking_raw:
            usuario = usuarios_por_id.get(row["criado_por_id"])
            if not usuario:
                continue
            dados = _dados_usuario(usuario)
            ranking_pessoas.append(
                {
                    "nome": dados["nome"] or usuario.username,
                    "ramal": dados["ramal"] or "-",
                    "email": dados["email"] or "-",
                    "cargo": dados["cargo"] or "-",
                    "setor": dados["setor"] or "-",
                    "celular": dados["celular"] or "",
                    "whatsapp": dados["whatsapp"] or "",
                    "localizacao": dados["localizacao"] or "-",
                    "foto_url": dados["foto_url"] or "",
                    "iniciais": dados["iniciais"] or "",
                    "total": row["total"],
                }
            )
        context["ranking_pessoas"] = ranking_pessoas
        return context


@acl_required("reserva_espacos", nivel_minimo=RegraAcesso.NIVEL_LEITURA)
def reserva_dashboard_exportar(request):
    """Exporta para XLSX as reservas filtradas a partir dos gráficos do dashboard."""

    if not user_is_fiscal(request.user):
        raise PermissionDenied

    try:
        from openpyxl import Workbook
    except ModuleNotFoundError as exc:
        raise RuntimeError("Instale openpyxl para habilitar a exportação do dashboard.") from exc

    queryset = ReservaRecurso.objects.select_related("objeto", "criado_por", "criado_por__perfil").order_by(
        "-data",
        "-hora_inicio",
    )
    partes_nome = ["reserva-espacos-dashboard"]

    mes_ref = (request.GET.get("mes_ref") or "").strip()
    if mes_ref:
        try:
            data_referencia = datetime.strptime(mes_ref, "%m/%Y").date()
        except ValueError:
            return HttpResponse(
                "Parâmetro mes_ref inválido. Use MM/YYYY.",
                status=400,
                content_type="text/plain; charset=utf-8",
            )
        inicio_mes = data_referencia.replace(day=1)
        fim_mes = data_referencia.replace(day=monthrange(data_referencia.year, data_referencia.month)[1])
        queryset = queryset.filter(data__range=(inicio_mes, fim_mes))
        partes_nome.append(data_referencia.strftime("%Y-%m"))

    objeto_label = (request.GET.get("objeto_label") or "").strip()
    if objeto_label:
        nome_objeto = objeto_label.split(" (")[0]
        queryset = queryset.filter(objeto__nome=nome_objeto)
        partes_nome.append("objeto")

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Reservas"
    sheet.append(
        [
            "ID",
            "Status",
            "Data",
            "Hora início",
            "Hora fim",
            "Objeto",
            "Localização",
            "Título",
            "Responsável",
            "Criado por",
            "Ramal",
            "E-mail",
        ]
    )

    for reserva in queryset:
        dados = _dados_usuario(reserva.criado_por)
        sheet.append(
            [
                reserva.pk,
                reserva.get_status_display(),
                reserva.data.strftime("%d/%m/%Y"),
                reserva.hora_inicio.strftime("%H:%M"),
                reserva.hora_fim.strftime("%H:%M"),
                reserva.objeto.nome,
                reserva.objeto.localizacao,
                reserva.titulo,
                reserva.responsavel,
                dados["nome"],
                dados["ramal"],
                dados["email"],
            ]
        )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = "-".join(partes_nome) + ".xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


class ConfiguracaoUpdateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Permite ajustar o grupo operacional dos fiscais do módulo."""

    model = ConfiguracaoReservaEspacos
    form_class = ConfiguracaoReservaEspacosForm
    template_name = "reserva_espacos/configuracao_form.html"
    success_url = reverse_lazy("reserva_espacos:configuracao")

    def get_object(self, queryset=None):
        return ConfiguracaoReservaEspacos.singleton()

    def test_func(self):
        return _pode_analisar(self)

    def form_valid(self, form):
        messages.success(self.request, "Configuração atualizada com sucesso.")
        return super().form_valid(form)
