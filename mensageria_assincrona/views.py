# Criado por OpenAI Codex em 12/06/2026
# Implementa caixa de entrada, painel administrativo e endpoints internos do módulo.

from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, JsonResponse
from django.db.models import Case, IntegerField, Value, When
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from acls.mixins import ACLRequiredMixin
from acls.models import RegraAcesso

from .forms import MensagemForm
from .models import Mensagem, MensagemDestino
from .services import (
    agendar_mensagem,
    cancelar_mensagem,
    indicadores_pendencias_usuario,
    listar_pendentes_usuario,
    marcar_ciente,
    marcar_visualizacao,
    mensagens_admin_queryset,
    publicar_mensagem,
    registrar_evento,
)


class MensageriaAdminMixin(LoginRequiredMixin, ACLRequiredMixin):
    """Restringe a área de gestão à permissão total do recurso."""

    recurso_slug = "mensageria_assincrona"
    acl_nivel_minimo = RegraAcesso.NIVEL_CONTROLE_TOTAL


class MinhasMensagensListView(LoginRequiredMixin, ListView):
    """Lista o histórico do usuário com filtros de status e período."""

    template_name = "mensageria_assincrona/minhas_list.html"
    context_object_name = "destinos"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            MensagemDestino.objects.filter(usuario=self.request.user)
            .select_related("mensagem", "mensagem__criada_por")
            .annotate(
                unread_order=Case(
                    When(status_destinatario=MensagemDestino.StatusDestinatario.PENDENTE, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            )
            .order_by("unread_order", "-entregue_em", "-id")
        )
        status = self.request.GET.get("status", "").strip()
        if status == "PENDENTE":
            queryset = queryset.filter(status_destinatario=MensagemDestino.StatusDestinatario.PENDENTE)
        elif status == "CIENTE":
            queryset = queryset.filter(status_destinatario=MensagemDestino.StatusDestinatario.CIENTE)

        data_inicio = self.request.GET.get("inicio", "").strip()
        if data_inicio:
            queryset = queryset.filter(entregue_em__date__gte=data_inicio)
        data_fim = self.request.GET.get("fim", "").strip()
        if data_fim:
            queryset = queryset.filter(entregue_em__date__lte=data_fim)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status_atual"] = self.request.GET.get("status", "")
        context["inicio_atual"] = self.request.GET.get("inicio", "")
        context["fim_atual"] = self.request.GET.get("fim", "")
        context["pendentes_ativas"] = listar_pendentes_usuario(self.request.user).count()
        return context


class MinhaMensagemDetailView(LoginRequiredMixin, DetailView):
    """Exibe o conteúdo completo da mensagem do próprio usuário."""

    template_name = "mensageria_assincrona/minha_detail.html"
    context_object_name = "destino"

    def get_queryset(self):
        return MensagemDestino.objects.filter(usuario=self.request.user).select_related("mensagem", "mensagem__criada_por")

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.status_destinatario == MensagemDestino.StatusDestinatario.PENDENTE and not obj.esta_expirada:
            marcar_ciente(obj, self.request.user)
            obj.refresh_from_db()
        else:
            marcar_visualizacao(obj, self.request.user)
            obj.refresh_from_db()
        return obj


class MensagemAdminListView(MensageriaAdminMixin, ListView):
    """Lista mensagens administrativas com filtro por status."""

    template_name = "mensageria_assincrona/admin_list.html"
    context_object_name = "mensagens"
    paginate_by = 20
    sort_map = {
        "id": "id",
        "assunto": "assunto",
        "corpo": "corpo",
        "prioridade": "prioridade",
        "status_envio": "status_envio",
        "origem_tipo": "origem_tipo",
        "origem_app": "origem_app",
        "origem_model": "origem_model",
        "origem_pk": "origem_pk",
        "criada_por": "criada_por__username",
        "publicar_em": "publicar_em",
        "publicada_em": "publicada_em",
        "expira_em": "expira_em",
        "payload_email": "payload_email",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    def get_queryset(self):
        queryset = mensagens_admin_queryset()
        status = self.request.GET.get("status", "").strip()
        if status in Mensagem.StatusEnvio.values:
            queryset = queryset.filter(status_envio=status)

        sort_key = self.request.GET.get("sort", "").strip()
        sort_dir = self.request.GET.get("dir", "desc").strip().lower()
        sort_field = self.sort_map.get(sort_key, "created_at")
        prefixo = "" if sort_dir == "asc" else "-"
        return queryset.order_by(f"{prefixo}{sort_field}", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_atual = self.request.GET.get("status", "")
        current_sort = self.request.GET.get("sort", "").strip() or "created_at"
        current_dir = self.request.GET.get("dir", "desc").strip().lower()

        if current_sort not in self.sort_map:
            current_sort = "created_at"
        if current_dir not in {"asc", "desc"}:
            current_dir = "desc"

        context["status_atual"] = status_atual
        context["status_opcoes"] = Mensagem.StatusEnvio.choices
        context["current_sort"] = current_sort
        context["current_dir"] = current_dir
        context["sort_links"] = {
            chave: self._build_sort_link(chave, status_atual, current_sort, current_dir)
            for chave in self.sort_map
        }
        return context

    def _build_sort_link(self, sort_key, status_atual, current_sort, current_dir):
        """Preserva filtros ativos ao alternar a ordenação de cada coluna."""

        proxima_direcao = "desc" if current_sort == sort_key and current_dir == "asc" else "asc"
        query = {"sort": sort_key, "dir": proxima_direcao}
        if status_atual:
            query["status"] = status_atual
        return f"?{urlencode(query)}"


class MensagemAdminCreateView(MensageriaAdminMixin, CreateView):
    """Cria mensagens manuais e decide o fluxo de publicação escolhido."""

    model = Mensagem
    form_class = MensagemForm
    template_name = "mensageria_assincrona/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Nova mensagem"
        context["voltar_url"] = reverse("mensageria:admin_list")
        return context

    def get_success_url(self):
        return reverse("mensageria:admin_detail", args=[self.object.pk])

    def form_valid(self, form):
        form.instance.criada_por = self.request.user
        form.instance.payload_email = form.cleaned_data.get("payload_email") or {}
        response = super().form_valid(form)
        registrar_evento(self.object, "CRIACAO", usuario=self.request.user)
        self._persistir_fluxo_publicacao(form)
        messages.success(self.request, "Mensagem salva.")
        return response

    def _persistir_fluxo_publicacao(self, form):
        modo = form.cleaned_data["modo_publicacao"]
        if modo == MensagemForm.ModoPublicacao.IMEDIATA:
            publicar_mensagem(self.object, usuario=self.request.user)
        elif modo == MensagemForm.ModoPublicacao.AGENDADA:
            agendar_mensagem(self.object, form.cleaned_data["publicar_em"], usuario=self.request.user)


class MensagemAdminUpdateView(MensageriaAdminMixin, UpdateView):
    """Edita mensagens apenas enquanto ainda não foram publicadas nem canceladas."""

    model = Mensagem
    form_class = MensagemForm
    template_name = "mensageria_assincrona/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.object.pode_editar:
            messages.warning(request, "Mensagens publicadas ou canceladas são somente leitura.")
            return redirect("mensageria:admin_detail", pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Editar mensagem"
        context["voltar_url"] = reverse("mensageria:admin_detail", args=[self.object.pk])
        return context

    def get_success_url(self):
        return reverse("mensageria:admin_detail", args=[self.object.pk])

    def form_valid(self, form):
        form.instance.payload_email = form.cleaned_data.get("payload_email") or {}
        response = super().form_valid(form)
        registrar_evento(self.object, "EDICAO", usuario=self.request.user, payload={"mensagem_id": self.object.pk})
        modo = form.cleaned_data["modo_publicacao"]
        if modo == MensagemForm.ModoPublicacao.IMEDIATA:
            publicar_mensagem(self.object, usuario=self.request.user)
        elif modo == MensagemForm.ModoPublicacao.AGENDADA:
            agendar_mensagem(self.object, form.cleaned_data["publicar_em"], usuario=self.request.user)
        else:
            self.object.status_envio = Mensagem.StatusEnvio.RASCUNHO
            self.object.publicar_em = None
            self.object.save(update_fields=["status_envio", "publicar_em", "updated_at"])
        messages.success(self.request, "Mensagem atualizada.")
        return response


class MensagemAdminDetailView(MensageriaAdminMixin, DetailView):
    """Mostra a mensagem, a audiência original e o estado dos destinatários."""

    model = Mensagem
    template_name = "mensageria_assincrona/admin_detail.html"
    context_object_name = "mensagem"

    def get_queryset(self):
        return mensagens_admin_queryset().prefetch_related(
            "destinos__usuario",
            "eventos__usuario",
            "audiencia_usuarios__usuario",
            "audiencia_setores__setor__group",
        )


class MensagemCancelarView(MensageriaAdminMixin, View):
    """Cancela mensagens ainda não publicadas."""

    def post(self, request, pk):
        mensagem = get_object_or_404(Mensagem, pk=pk)
        cancelar_mensagem(mensagem, usuario=request.user)
        messages.success(request, "Mensagem cancelada.")
        return redirect("mensageria:admin_detail", pk=pk)


class MensagemCienteView(LoginRequiredMixin, View):
    """Recebe a confirmação explícita de ciência do usuário."""

    def post(self, request):
        destino = get_object_or_404(MensagemDestino, pk=request.POST.get("destino_id"))
        try:
            marcar_ciente(destino, request.user)
        except PermissionError:
            raise Http404("Mensagem não encontrada.")
        messages.success(request, "Ciência registrada.")
        next_url = request.POST.get("next_url") or reverse("mensageria:minhas")
        return redirect(next_url)


class MensagemVisualizadaView(LoginRequiredMixin, View):
    """Marca a primeira visualização sem alterar o status de ciência."""

    def post(self, request):
        destino = get_object_or_404(MensagemDestino, pk=request.POST.get("destino_id"))
        try:
            marcar_visualizacao(destino, request.user)
        except PermissionError:
            raise Http404("Mensagem não encontrada.")
        return JsonResponse({"ok": True})


class MensageriaIndicadoresView(LoginRequiredMixin, View):
    """Exibe contagem pendente e primeira mensagem para futuras integrações assíncronas."""

    def get(self, request):
        return JsonResponse(indicadores_pendencias_usuario(request.user))
