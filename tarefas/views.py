# Criado por OpenAI Codex em 23/06/2026
# Implementa onboarding, dashboard pessoal, detalhe, histórico e movimentação de status do módulo.

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, UpdateView

from acls.mixins import ACLRequiredMixin
from acls.models import RegraAcesso
from usuarios.services import ensure_usuario_perfil

from .forms import SuperiorImediatoForm, TarefaBuscaForm, TarefaForm, TarefaHistoricoBuscaForm, TarefaHistoricoForm, TarefaPrazoForm
from .models import Tarefa, TarefaHistorico
from .services import (
    STATUS_OPERACIONAIS,
    calcular_resumo_carga_usuario,
    enriquecer_tarefa_para_interface,
    gestor_pode_ver_usuario,
    gestor_tem_visao_gerencial,
    listar_liderados_imediatos,
    montar_card_gerencial_usuario,
    montar_cards_gerenciais,
    mover_tarefa_status,
    queryset_historico_tarefa,
    queryset_macro_usuario,
    registrar_historico,
    resolver_escopo_gerencial,
)

User = get_user_model()


class TarefasMixin(LoginRequiredMixin, ACLRequiredMixin):
    """Conecta o app ao ACL e garante perfil completo de entrada."""

    recurso_slug = "tarefas"
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def dispatch(self, request, *args, **kwargs):
        self.perfil = ensure_usuario_perfil(request.user)
        return super().dispatch(request, *args, **kwargs)


class TarefasSuperiorObrigatorioMixin(TarefasMixin):
    """Bloqueia o uso do módulo enquanto o superior imediato não for definido."""

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if not self.perfil.superior_imediato_id:
            if request.resolver_match and request.resolver_match.url_name != "onboarding":
                messages.warning(request, "Antes de usar o módulo de tarefas, informe o seu superior imediato.")
                return redirect("tarefas:onboarding")
        return response


class TarefasOnboardingView(TarefasMixin, FormView):
    """Recebe o superior imediato no primeiro acesso ao módulo."""

    form_class = SuperiorImediatoForm
    template_name = "tarefas/onboarding.html"

    def dispatch(self, request, *args, **kwargs):
        self.perfil = ensure_usuario_perfil(request.user)
        if self.perfil.superior_imediato_id:
            return redirect("tarefas:list")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = self.perfil
        kwargs["current_user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Superior imediato registrado com sucesso.")
        return redirect("tarefas:list")


class TarefaListView(TarefasSuperiorObrigatorioMixin, FormView):
    """Entrega a visão pessoal em tabela ou kanban com busca, filtros e ordenação."""

    template_name = "tarefas/tarefa_list.html"
    form_class = TarefaBuscaForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["data"] = self.request.GET or None
        return kwargs

    def get_view_mode(self):
        view_mode = (self.request.GET.get("view") or "table").strip().lower()
        return view_mode if view_mode in {"table", "kanban"} else "table"

    def get_dashboard_mode(self):
        dashboard_mode = (self.request.GET.get("dashboard") or "mine").strip().lower()
        return dashboard_mode if dashboard_mode in {"mine", "team"} else "mine"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dashboard_mode = self.get_dashboard_mode()
        team_access = gestor_tem_visao_gerencial(self.request.user)
        if dashboard_mode == "team":
            if not team_access:
                raise PermissionDenied("Você não possui equipe vinculada para acessar esta visão.")
            scope = (self.request.GET.get("scope") or "imediatos").strip().lower()
            scope_data = resolver_escopo_gerencial(self.request.user, scope)
            cards = montar_cards_gerenciais(scope_data["usuarios"])
            context.update(
                {
                    "dashboard_mode": "team",
                    "team_access": team_access,
                    "team_scope": scope_data["scope"],
                    "team_scope_label": scope_data["label"],
                    "team_cards": cards,
                    "page_title": "Minha equipe",
                    "page_description": "Acompanhe a carga de trabalho da sua equipe por escopo hierárquico.",
                }
            )
            return context

        termo = self.request.GET.get("q", "")
        prioridade = self.request.GET.get("prioridade", "")
        status = self.request.GET.get("status", "")
        order_by = self.request.GET.get("order_by", "prazo")
        direction = self.request.GET.get("direction", "asc")
        view_mode = self.get_view_mode()
        tarefas_qs = queryset_macro_usuario(
            self.request.user,
            termo=termo,
            prioridade=prioridade,
            status=status,
            order_by=order_by,
            direction=direction,
        )
        resumo_carga = calcular_resumo_carga_usuario(tarefas_qs)
        tarefas = [enriquecer_tarefa_para_interface(tarefa) for tarefa in tarefas_qs]
        kanban = {
            status_coluna: [tarefa for tarefa in tarefas if tarefa.status == status_coluna]
            for status_coluna in STATUS_OPERACIONAIS
        }
        context["tarefas"] = tarefas
        context["kanban"] = kanban
        context["dashboard_mode"] = dashboard_mode
        context["team_access"] = team_access
        context["view_mode"] = view_mode
        context["current_order_by"] = order_by
        context["current_direction"] = direction
        context["current_status"] = status
        context["resumo"] = {
            "total": len([t for t in tarefas if t.status != Tarefa.Status.ARQUIVADA]),
            "criticas": len([t for t in tarefas if t.status != Tarefa.Status.ARQUIVADA and t.prioridade == Tarefa.Prioridade.CRITICA]),
            "vencendo_hoje": len(
                [t for t in tarefas if t.status != Tarefa.Status.ARQUIVADA and t.prazo.date() == timezone.localdate()]
            ),
            "atrasadas": resumo_carga["atrasadas"],
            "carga_total": resumo_carga["carga_total"],
            "faixa_ocupacao": resumo_carga["faixa_ocupacao"],
        }
        context["page_title"] = "Minhas tarefas"
        context["page_description"] = "Gerencie suas tarefas em tabela inteligente ou kanban com histórico completo."
        context["sort_urls"] = self.build_sort_urls()
        return context

    def build_sort_urls(self):
        """Preserva filtros atuais enquanto alterna ordenações da tabela."""

        urls = {}
        for campo in ("id", "titulo", "prazo", "criado_por", "responsavel", "atualizado_em"):
            query = self.request.GET.copy()
            query["view"] = "table"
            query["order_by"] = campo
            if self.request.GET.get("order_by") == campo and self.request.GET.get("direction", "asc") == "asc":
                query["direction"] = "desc"
            else:
                query["direction"] = "asc"
            urls[campo] = f"{reverse('tarefas:list')}?{query.urlencode()}"
        return urls


class TarefaCreateView(TarefasSuperiorObrigatorioMixin, CreateView):
    """Cria uma nova tarefa do usuário atual e inicia seu histórico."""

    model = Tarefa
    form_class = TarefaForm
    template_name = "tarefas/tarefa_form.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        form.instance.responsavel = self.request.user
        form.instance.status = Tarefa.Status.PENDENTE
        response = super().form_valid(form)
        registrar_historico(
            tarefa=self.object,
            autor=self.request.user,
            tipo_evento=TarefaHistorico.TipoEvento.CRIACAO,
            titulo_evento="Tarefa criada",
            descricao_evento=f"Tarefa criada com prazo em {self.object.prazo:%d/%m/%Y %H:%M}.",
        )
        messages.success(self.request, "Tarefa criada com sucesso.")
        return response

    def get_success_url(self):
        return reverse("tarefas:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nova tarefa"
        context["page_description"] = "Registre o título, a descrição, o prazo e a prioridade da sua tarefa."
        context["submit_label"] = "Salvar tarefa"
        return context


class TarefaOwnershipMixin(TarefasSuperiorObrigatorioMixin):
    """Restringe o acesso às tarefas do universo do usuário atual."""

    def get_queryset(self):
        return Tarefa.objects.do_usuario(self.request.user).select_related("criado_por__perfil", "responsavel__perfil")

    def get_object(self, queryset=None):
        tarefa = super().get_object(queryset)
        if not tarefa.permite_edicao_por(self.request.user):
            raise PermissionDenied("Você só pode acessar tarefas criadas por você ou atribuídas a você.")
        return tarefa


class TarefaReadAccessMixin(TarefasSuperiorObrigatorioMixin):
    """Permite leitura da própria tarefa e também leitura gerencial do escopo permitido."""

    def get_queryset(self):
        return Tarefa.objects.select_related("criado_por__perfil", "responsavel__perfil")

    def get_object(self, queryset=None):
        tarefa = super().get_object(queryset)
        if tarefa.permite_edicao_por(self.request.user):
            return tarefa
        if gestor_tem_visao_gerencial(self.request.user) and (
            gestor_pode_ver_usuario(self.request.user, tarefa.responsavel)
            or gestor_pode_ver_usuario(self.request.user, tarefa.criado_por)
        ):
            return tarefa
        raise PermissionDenied("Você não possui acesso a esta tarefa.")


class TarefaDetailView(TarefaReadAccessMixin, DetailView):
    """Exibe a tarefa e sua linha do tempo pesquisável."""

    model = Tarefa
    template_name = "tarefas/tarefa_detail.html"
    context_object_name = "tarefa"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        termo = self.request.GET.get("q", "")
        filtro = self.request.GET.get("tipo", "")
        tarefa = enriquecer_tarefa_para_interface(self.object)
        context["tarefa"] = tarefa
        context["historico_form"] = TarefaHistoricoForm()
        context["prazo_form"] = TarefaPrazoForm(instance=tarefa)
        context["busca_form"] = TarefaHistoricoBuscaForm(self.request.GET or None)
        context["historicos"] = queryset_historico_tarefa(tarefa, termo=termo, filtro=filtro)
        context["page_title"] = f"Tarefa #{tarefa.pk}"
        context["status_operacionais"] = STATUS_OPERACIONAIS
        return context


class TarefaUpdateView(TarefaOwnershipMixin, UpdateView):
    """Permite editar os dados principais da tarefa e registra o acontecimento."""

    model = Tarefa
    form_class = TarefaForm
    template_name = "tarefas/tarefa_form.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def form_valid(self, form):
        response = super().form_valid(form)
        registrar_historico(
            tarefa=self.object,
            autor=self.request.user,
            tipo_evento=TarefaHistorico.TipoEvento.EDICAO,
            titulo_evento="Tarefa editada",
            descricao_evento="Os dados principais da tarefa foram atualizados.",
        )
        messages.success(self.request, "Tarefa atualizada com sucesso.")
        return response

    def get_success_url(self):
        return reverse("tarefas:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Editar tarefa #{self.object.pk}"
        context["page_description"] = "Atualize o conteúdo principal da tarefa."
        context["submit_label"] = "Salvar alterações"
        return context


class TarefaPrazoUpdateView(TarefaOwnershipMixin, UpdateView):
    """Muda o prazo e exige justificativa registrada em histórico."""

    model = Tarefa
    form_class = TarefaPrazoForm
    template_name = "tarefas/tarefa_prazo_form.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def form_valid(self, form):
        prazo_anterior = self.object.prazo
        response = super().form_valid(form)
        registrar_historico(
            tarefa=self.object,
            autor=self.request.user,
            tipo_evento=TarefaHistorico.TipoEvento.ALTERACAO_PRAZO,
            titulo_evento="Prazo alterado",
            descricao_evento=form.cleaned_data["justificativa"],
            prazo_anterior=prazo_anterior,
            prazo_novo=self.object.prazo,
        )
        messages.success(self.request, "Prazo alterado com sucesso.")
        return response

    def get_success_url(self):
        return reverse("tarefas:detail", args=[self.object.pk])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = f"Alterar prazo da tarefa #{self.object.pk}"
        context["page_description"] = "Informe o novo prazo e a justificativa da alteração."
        context["submit_label"] = "Salvar novo prazo"
        return context


class TarefaHistoricoCreateView(TarefaOwnershipMixin, FormView):
    """Adiciona comentário e/ou anexo na linha do tempo da tarefa."""

    form_class = TarefaHistoricoForm
    template_name = "tarefas/tarefa_detail.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def dispatch(self, request, *args, **kwargs):
        self.tarefa = get_object_or_404(Tarefa.objects.do_usuario(request.user), pk=kwargs["pk"])
        if not self.tarefa.permite_edicao_por(request.user):
            raise PermissionDenied("Você só pode alterar tarefas criadas por você ou atribuídas a você.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["files"] = self.request.FILES or None
        return kwargs

    def form_valid(self, form):
        comentario = (form.cleaned_data.get("comentario") or "").strip()
        arquivo = form.cleaned_data.get("arquivo")
        tipo = TarefaHistorico.TipoEvento.COMENTARIO if comentario else TarefaHistorico.TipoEvento.ANEXO
        titulo = "Comentário adicionado" if comentario else "Anexo adicionado"
        registrar_historico(
            tarefa=self.tarefa,
            autor=self.request.user,
            tipo_evento=tipo,
            titulo_evento=titulo,
            comentario=comentario,
            arquivo=arquivo,
            descricao_evento="Comentário e anexo registrados no histórico." if comentario and arquivo else "",
        )
        messages.success(self.request, "Histórico atualizado com sucesso.")
        return redirect("tarefas:detail", pk=self.tarefa.pk)


class TarefaStatusUpdateView(TarefasSuperiorObrigatorioMixin, View):
    """Move tarefas entre status operacionais via formulário comum ou AJAX."""

    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def post(self, request, pk):
        tarefa = get_object_or_404(Tarefa.objects.do_usuario(request.user).select_related("criado_por__perfil", "responsavel__perfil"), pk=pk)
        if not tarefa.permite_edicao_por(request.user):
            raise PermissionDenied("Você não pode mover esta tarefa.")
        novo_status = request.POST.get("status")
        try:
            tarefa = mover_tarefa_status(tarefa=tarefa, novo_status=novo_status, autor=request.user)
        except ValidationError as exc:
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": False, "error": str(exc)}, status=400)
            messages.error(request, str(exc))
            return redirect("tarefas:detail", pk=tarefa.pk)

        tarefa = enriquecer_tarefa_para_interface(tarefa)
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "ok": True,
                    "tarefa": {
                        "id": tarefa.pk,
                        "titulo": tarefa.titulo,
                        "status": tarefa.status,
                        "status_label": tarefa.get_status_display(),
                        "detail_url": reverse("tarefas:detail", args=[tarefa.pk]),
                        "prazo": tarefa.prazo.strftime("%d/%m/%Y %H:%M"),
                        "progresso": tarefa.progresso_prazo,
                    },
                }
            )
        messages.success(request, "Status da tarefa atualizado com sucesso.")
        return redirect("tarefas:detail", pk=tarefa.pk)


class TarefasPessoaGerencialView(TarefasSuperiorObrigatorioMixin, FormView):
    """Detalha um colaborador da equipe com resumo, subordinados e tarefas próprias."""

    template_name = "tarefas/tarefa_team_detail.html"
    form_class = TarefaBuscaForm

    def dispatch(self, request, *args, **kwargs):
        if not gestor_tem_visao_gerencial(request.user):
            raise PermissionDenied("Você não possui equipe vinculada para acessar esta visão.")
        self.pessoa = get_object_or_404(User.objects.select_related("perfil"), pk=kwargs["user_id"], is_active=True)
        if not gestor_pode_ver_usuario(request.user, self.pessoa):
            raise PermissionDenied("Este colaborador não está no seu escopo gerencial.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["data"] = self.request.GET or None
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        termo = self.request.GET.get("q", "")
        prioridade = self.request.GET.get("prioridade", "")
        status = self.request.GET.get("status", "")
        order_by = self.request.GET.get("order_by", "prazo")
        direction = self.request.GET.get("direction", "asc")
        tarefas_qs = queryset_macro_usuario(
            self.pessoa,
            termo=termo,
            prioridade=prioridade,
            status=status,
            order_by=order_by,
            direction=direction,
        )
        tarefas = [enriquecer_tarefa_para_interface(tarefa) for tarefa in tarefas_qs]
        subordinados = list(listar_liderados_imediatos(self.pessoa))
        context.update(
            {
                "dashboard_mode": "team",
                "team_access": True,
                "page_title": f"Equipe: {self.pessoa.perfil.nome_completo or self.pessoa.username}",
                "page_description": "Resumo gerencial do colaborador, seus subordinados e suas tarefas operacionais.",
                "pessoa": self.pessoa,
                "person_card": montar_card_gerencial_usuario(self.pessoa),
                "subordinate_cards": montar_cards_gerenciais(subordinados),
                "tarefas": tarefas,
                "sort_urls": self.build_sort_urls(),
            }
        )
        return context

    def build_sort_urls(self):
        """Monta URLs de ordenação mantendo filtros no detalhe gerencial da pessoa."""

        urls = {}
        for campo in ("id", "titulo", "prazo", "criado_por", "responsavel", "atualizado_em"):
            query = self.request.GET.copy()
            query["order_by"] = campo
            if self.request.GET.get("order_by") == campo and self.request.GET.get("direction", "asc") == "asc":
                query["direction"] = "desc"
            else:
                query["direction"] = "asc"
            urls[campo] = f"{reverse('tarefas:team_person', args=[self.pessoa.pk])}?{query.urlencode()}"
        return urls


def bad_request(request, message):
    """Responde erro simples para chamadas inválidas sem vazar stack para a interface."""

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": False, "error": message}, status=400)
    return HttpResponseBadRequest(message)
