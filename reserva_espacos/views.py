"""Views do módulo de reserva de espaços."""

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
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from acls.mixins import ACLRequiredMixin, acl_required
from acls.models import RegraAcesso

from .forms import ObjetoReservavelForm, ReservaRecursoForm
from .models import ObjetoReservavel, ReservaRecurso


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


def _usuario_pode_criar_reserva(user, acl_level: str | None) -> bool:
    """Usuário pode criar reserva quando tem modificação ou controle total."""

    if not getattr(user, "is_authenticated", False):
        return False
    return acl_level in {RegraAcesso.NIVEL_MODIFICACAO, RegraAcesso.NIVEL_CONTROLE_TOTAL}


def _usuario_pode_gerenciar_objeto(user, objeto: ObjetoReservavel, acl_level: str | None) -> bool:
    """Sem categoria, o CRUD de objetos fica restrito ao controle total."""

    return acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL


def _usuario_pode_gerenciar_reserva(user, reserva: ReservaRecurso, acl_level: str | None) -> bool:
    """Define quem pode alterar qualquer reserva além do próprio autor."""

    if acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL:
        return True
    return reserva.criado_por_id == getattr(user, "id", None)


class ReservasRecursosMixin(ACLRequiredMixin):
    """Mixin base do módulo com slug fixo e contexto de permissões auxiliares."""

    recurso_slug = "reserva_espacos"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        acl_level = _nivel_usuario(self)
        context["reservas_acl_level"] = acl_level
        context["pode_criar_reserva"] = _usuario_pode_criar_reserva(self.request.user, acl_level)
        context["pode_gerenciar_objetos"] = acl_level == RegraAcesso.NIVEL_CONTROLE_TOTAL
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
        reservas_data = []
        for reserva in reservas:
            dados = _dados_usuario(reserva.criado_por)
            reservas_data.append(
                {
                    "id": reserva.pk,
                    "objeto_id": reserva.objeto_id,
                    "objeto_nome": reserva.objeto.nome,
                    "objeto_localizacao": reserva.objeto.localizacao,
                    "cor": reserva.objeto.cor,
                    "titulo": reserva.titulo,
                    "responsavel": reserva.responsavel,
                    "observacoes": reserva.observacoes,
                    "inicio": datetime.combine(reserva.data, reserva.hora_inicio).isoformat(),
                    "fim": datetime.combine(reserva.data, reserva.hora_fim).isoformat(),
                    "criado_por_nome": dados["nome"],
                    "criado_por_nome_curto": dados["nome_curto"],
                    "criado_por_ramal": dados["ramal"],
                    "criado_por_email": dados["email"],
                    "url": reverse("reserva_espacos:reserva_detail", kwargs={"pk": reserva.pk}),
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

    def get_queryset(self):
        return ObjetoReservavel.objects.order_by("nome")


class ObjetoCreateView(ReservasRecursosMixin, LoginRequiredMixin, CreateView):
    """Cria objetos; sem categorias, o cadastro é administração global."""

    model = ObjetoReservavel
    form_class = ObjetoReservavelForm
    template_name = "reserva_espacos/objeto_form.html"
    success_url = reverse_lazy("reserva_espacos:objeto_list")
    acl_nivel_minimo = RegraAcesso.NIVEL_CONTROLE_TOTAL

    def form_valid(self, form):
        messages.success(self.request, "Objeto cadastrado com sucesso.")
        return super().form_valid(form)


class ObjetoUpdateView(ReservasRecursosMixin, LoginRequiredMixin, UpdateView):
    """Edita objetos existentes no escopo administrativo global."""

    model = ObjetoReservavel
    form_class = ObjetoReservavelForm
    template_name = "reserva_espacos/objeto_form.html"
    success_url = reverse_lazy("reserva_espacos:objeto_list")
    acl_nivel_minimo = RegraAcesso.NIVEL_CONTROLE_TOTAL

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _usuario_pode_gerenciar_objeto(request.user, self.object, _nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Objeto atualizado com sucesso.")
        return super().form_valid(form)


class ObjetoDeleteView(ReservasRecursosMixin, LoginRequiredMixin, DeleteView):
    """Exclui objetos somente no escopo administrativo global."""

    model = ObjetoReservavel
    template_name = "reserva_espacos/objeto_confirm_delete.html"
    success_url = reverse_lazy("reserva_espacos:objeto_list")
    acl_nivel_minimo = RegraAcesso.NIVEL_CONTROLE_TOTAL

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not _usuario_pode_gerenciar_objeto(request.user, self.object, _nivel_usuario(self)):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reservas_relacionadas"] = self.object.reservas.count()
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Objeto excluído com sucesso.")
        return super().delete(request, *args, **kwargs)


class ReservaListView(ReservasRecursosMixin, ListView):
    """Lista tabular de reservas com busca por múltiplos campos."""

    model = ReservaRecurso
    template_name = "reserva_espacos/reserva_list.html"
    context_object_name = "reservas"

    def get_queryset(self):
        queryset = ReservaRecurso.objects.select_related("objeto", "criado_por").all()
        query = (self.request.GET.get("q") or "").strip()
        if not query:
            return queryset
        filtros = (
            Q(titulo__icontains=query)
            | Q(responsavel__icontains=query)
            | Q(objeto__nome__icontains=query)
            | Q(objeto__localizacao__icontains=query)
        )
        for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                filtros |= Q(data=datetime.strptime(query, formato).date())
                break
            except ValueError:
                continue
        return queryset.filter(filtros)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = (self.request.GET.get("q") or "").strip()
        return context


class ReservaDetailView(ReservasRecursosMixin, DetailView):
    """Mostra todos os dados da reserva em página dedicada."""

    model = ReservaRecurso
    template_name = "reserva_espacos/reserva_detail.html"
    context_object_name = "reserva"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dados = _dados_usuario(self.object.criado_por)
        context["criador"] = dados
        context["pode_editar"] = _usuario_pode_gerenciar_reserva(self.request.user, self.object, _nivel_usuario(self))
        if self.object.serie_id:
            context["serie_count"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).count()
        return context


class ReservaCreateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Cria reservas simples ou recorrentes conforme a seleção do formulário."""

    model = ReservaRecurso
    form_class = ReservaRecursoForm
    template_name = "reserva_espacos/reserva_form.html"
    success_url = reverse_lazy("reserva_espacos:reserva_list")
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def test_func(self):
        return _usuario_pode_criar_reserva(self.request.user, _nivel_usuario(self))

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

    def form_valid(self, form):
        recurrence_dates = form.get_recurrence_dates()
        dados = form.cleaned_data
        responsavel = _nome_usuario_responsavel(self.request.user)
        if recurrence_dates and len(recurrence_dates) > 1:
            serie_id = uuid.uuid4()
            for occ_date in recurrence_dates:
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
            messages.success(self.request, "Série de reservas criada com sucesso.")
            return redirect(self.success_url)
        form.instance.criado_por = self.request.user
        form.instance.responsavel = responsavel
        messages.success(self.request, "Reserva criada com sucesso.")
        return super().form_valid(form)


class ReservaUpdateView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edita uma reserva ou a série inteira quando o usuário tem essa autorização."""

    model = ReservaRecurso
    form_class = ReservaRecursoForm
    template_name = "reserva_espacos/reserva_form.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def test_func(self):
        return _usuario_pode_gerenciar_reserva(self.request.user, self.get_object(), _nivel_usuario(self))

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
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
            messages.success(self.request, "Série de reservas atualizada com sucesso.")
            return redirect(self.get_success_url())
        messages.success(self.request, "Reserva atualizada com sucesso.")
        return super().form_valid(form)


class ReservaDeleteView(ReservasRecursosMixin, LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Remove uma única reserva ou todas as ocorrências da série."""

    model = ReservaRecurso
    template_name = "reserva_espacos/reserva_confirm_delete.html"
    success_url = reverse_lazy("reserva_espacos:reserva_list")
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def test_func(self):
        return _usuario_pode_gerenciar_reserva(self.request.user, self.get_object(), _nivel_usuario(self))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.object.serie_id:
            context["serie_count"] = ReservaRecurso.objects.filter(serie_id=self.object.serie_id).count()
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        apply_scope = request.POST.get("apply_scope", "single")
        if self.object.serie_id and apply_scope == "all":
            ReservaRecurso.objects.filter(serie_id=self.object.serie_id).delete()
            messages.success(self.request, "Série de reservas excluída com sucesso.")
            return redirect(self.success_url)
        messages.success(self.request, "Reserva excluída com sucesso.")
        return super().post(request, *args, **kwargs)


class ReservaDashboardView(ReservasRecursosMixin, ListView):
    """Dashboard analítico adaptado do app de referência para recursos genéricos."""

    model = ReservaRecurso
    template_name = "reserva_espacos/dashboard.html"
    context_object_name = "reservas"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reservas_base = ReservaRecurso.objects.select_related("criado_por", "criado_por__perfil", "objeto")
        hoje = timezone.localdate()
        inicio_mes = hoje.replace(day=1)
        fim_mes = hoje.replace(day=monthrange(hoje.year, hoje.month)[1])

        reservas_mes = reservas_base.filter(data__range=(inicio_mes, fim_mes))
        total_reservas_mes = reservas_mes.count()
        objetos_ativos_mes = reservas_mes.values("objeto_id").distinct().count()
        dias_com_reserva_mes = reservas_mes.values("data").distinct().count()
        media_reservas_por_dia = round(total_reservas_mes / dias_com_reserva_mes, 2) if dias_com_reserva_mes else 0

        reservas_por_mes = (
            reservas_base.annotate(mes=TruncMonth("data"))
            .values("mes")
            .annotate(total=Count("id"))
            .order_by("mes")
        )
        grafico_reservas_meses = {
            "labels": [item["mes"].strftime("%m/%Y") for item in reservas_por_mes if item["mes"]],
            "values": [item["total"] for item in reservas_por_mes if item["mes"]],
        }

        objetos_top = (
            reservas_base.values("objeto__nome")
            .annotate(total=Count("id"))
            .order_by("-total", "objeto__nome")
        )[:10]
        grafico_objetos_top = {
            "labels": [item["objeto__nome"] for item in objetos_top],
            "values": [item["total"] for item in objetos_top],
        }

        ranking_raw = list(
            reservas_base.filter(criado_por__isnull=False)
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

        context.update(
            {
                "total_reservas_mes": total_reservas_mes,
                "objetos_ativos_mes": objetos_ativos_mes,
                "media_reservas_por_dia": media_reservas_por_dia,
                "mes_referencia": hoje.strftime("%m/%Y"),
                "grafico_reservas_meses": grafico_reservas_meses,
                "grafico_objetos_top": grafico_objetos_top,
                "ranking_pessoas": ranking_pessoas,
            }
        )
        return context


@acl_required("reserva_espacos", nivel_minimo=RegraAcesso.NIVEL_LEITURA)
def reserva_dashboard_exportar(request):
    """Exporta para XLSX as reservas filtradas a partir dos gráficos do dashboard."""

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
