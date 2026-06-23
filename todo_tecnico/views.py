# Criado por OpenAI Codex em 19/06/2026
# Objetivo: Implementar listagem, criação, edição e mudança de estado do backlog técnico.

from django.contrib import messages
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView, View

from acls.mixins import ACLRequiredMixin
from acls.models import RegraAcesso

from .forms import (
    CodexAgendamentoForm,
    CodexConfiguracaoForm,
    TarefaTecnicaCadastroForm,
    TarefaTecnicaEdicaoConcluidaForm,
    TarefaTecnicaSolucaoForm,
)
from .models import CodexExecucao, TarefaTecnica
from .services import (
    disparar_worker_background,
    enfileirar_execucao,
    get_codex_configuracao,
    listar_execucoes_painel,
    normalizar_titulo_tarefa,
    obter_monitoramento_codex,
)


class TodoTecnicoMixin(ACLRequiredMixin):
    """Centraliza a integração do app com ACL e flags reutilizadas nos templates."""

    recurso_slug = "todo_tecnico"
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def dispatch(self, request, *args, **kwargs):
        """Mantém o módulo exclusivo para o usuário técnico root."""

        if not request.user.is_authenticated or request.user.username != "root":
            raise PermissionDenied("O módulo To-Do Técnico é restrito ao usuário root.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["todo_tecnico_acl_level"] = self.get_acl_level()
        return context


class TarefaOwnershipMixin(TodoTecnicoMixin):
    """Valida operações destrinchando a regra de propriedade para nível de modificação."""

    def get_object(self, queryset=None):
        tarefa = super().get_object(queryset=queryset)
        self._validar_acesso_objeto(tarefa)
        return tarefa

    def _validar_acesso_objeto(self, tarefa: TarefaTecnica) -> None:
        """Impede alterações em tarefas de terceiros quando o ACL for modificação."""

        if self.get_acl_level() == RegraAcesso.NIVEL_MODIFICACAO and tarefa.criado_por_id != self.request.user.id:
            raise PermissionDenied("Você só pode alterar tarefas técnicas que você mesmo criou.")


class TarefaTecnicaListView(TodoTecnicoMixin, ListView):
    """Exibe o backlog compartilhado com filtros simples e indicadores resumidos."""

    model = TarefaTecnica
    template_name = "todo_tecnico/tarefa_list.html"
    context_object_name = "tarefas"

    def get_queryset(self):
        situacao = self.request.GET.get("situacao", "abertas")
        minhas = self.request.GET.get("minhas", "")

        queryset = TarefaTecnica.objects.select_related("criado_por", "criado_por__perfil")
        if situacao == "concluidas":
            queryset = queryset.concluidas()
        elif situacao == "abertas":
            queryset = queryset.abertas()

        if minhas == "1":
            queryset = queryset.filter(criado_por=self.request.user)

        return queryset.annotate(
            ordem_aberta=Case(
                When(concluido_em__isnull=True, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by("ordem_aberta", "-criado_em", "-id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        configuracao = get_codex_configuracao()
        if CodexExecucao.objects.filter(status__in=[CodexExecucao.STATUS_AGENDADA, CodexExecucao.STATUS_NA_FILA]).exists():
            disparar_worker_background()
        resumo = TarefaTecnica.objects.aggregate(
            total=Count("id"),
            abertas=Count("id", filter=Q(concluido_em__isnull=True)),
            concluidas=Count("id", filter=Q(concluido_em__isnull=False)),
            minhas_abertas=Count(
                "id",
                filter=Q(concluido_em__isnull=True, criado_por=self.request.user),
            ),
        )
        context["resumo"] = resumo
        context["situacao_atual"] = self.request.GET.get("situacao", "abertas")
        context["somente_minhas"] = self.request.GET.get("minhas", "") == "1"
        context["codex_configuracao"] = configuracao
        context["codex_monitoramento"] = obter_monitoramento_codex(configuracao)
        context["codex_painel"] = listar_execucoes_painel()
        context["codex_config_form"] = CodexConfiguracaoForm(instance=configuracao)
        context["codex_agendamento_form"] = CodexAgendamentoForm()
        return context


class TarefaTecnicaCreateView(TodoTecnicoMixin, CreateView):
    """Cria uma nova tarefa e grava automaticamente o usuário autor do registro."""

    model = TarefaTecnica
    form_class = TarefaTecnicaCadastroForm
    template_name = "todo_tecnico/tarefa_form.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Nova tarefa técnica"
        context["page_description"] = "Registre a descrição obrigatória da pendência e use o título apenas se quiser resumir a demanda."
        context["submit_label"] = "Salvar"
        return context

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        messages.success(self.request, "Tarefa técnica criada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("todo_tecnico:list")


class TarefaTecnicaUpdateView(TarefaOwnershipMixin, UpdateView):
    """Edita apenas os dados de abertura da tarefa, mantendo a solução para o fluxo de conclusão."""

    model = TarefaTecnica
    form_class = TarefaTecnicaCadastroForm
    template_name = "todo_tecnico/tarefa_form.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def get_form_class(self):
        """Tarefas concluídas exibem a solução no mesmo formulário para revisão completa."""

        if self.object.esta_concluida:
            return TarefaTecnicaEdicaoConcluidaForm
        return TarefaTecnicaCadastroForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Editar tarefa técnica"
        if self.object.esta_concluida:
            context["page_description"] = "Revise título, descrição e solução para manter o histórico completo da tarefa concluída."
        else:
            context["page_description"] = "Ajuste o título opcional e a descrição da pendência sem mexer no registro da solução."
        context["submit_label"] = "Salvar"
        context["tarefa"] = self.object
        return context

    def form_valid(self, form):
        messages.success(self.request, "Tarefa técnica atualizada.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("todo_tecnico:list")


class TarefaTecnicaSolucionarView(TarefaOwnershipMixin, UpdateView):
    """Conclui a tarefa em uma tela própria, exibindo apenas o campo de solução."""

    model = TarefaTecnica
    form_class = TarefaTecnicaSolucaoForm
    template_name = "todo_tecnico/tarefa_form.html"
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Registrar solução"
        context["page_description"] = "Descreva a solução aplicada para concluir a tarefa técnica."
        context["submit_label"] = "Concluir tarefa"
        context["tarefa"] = self.object
        return context

    def form_valid(self, form):
        # A solução e a data de conclusão são gravadas no mesmo envio para manter o fechamento consistente.
        form.instance.concluido_em = timezone.now()
        messages.success(self.request, "Tarefa técnica concluída.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("todo_tecnico:list")


class TarefaTecnicaDetailView(TodoTecnicoMixin, DetailView):
    """Exibe o conteúdo integral da tarefa para consulta rápida a partir da listagem."""

    model = TarefaTecnica
    template_name = "todo_tecnico/tarefa_detail.html"
    context_object_name = "tarefa"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["execucoes_codex"] = self.object.execucoes_codex.order_by("-criado_em")[:12]
        context["titulo_sugerido"] = normalizar_titulo_tarefa(self.object)
        return context


class TarefaConclusaoBaseView(TarefaOwnershipMixin, View):
    """Compartilha a busca do objeto e o retorno para a listagem com mensagens."""

    model = TarefaTecnica
    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def get_object(self, queryset=None):
        return get_object_or_404(TarefaTecnica, pk=self.kwargs["pk"])

    def post(self, request, *args, **kwargs):
        tarefa = self.get_object()
        self._validar_acesso_objeto(tarefa)
        self.processar(tarefa)
        return HttpResponseRedirect(reverse("todo_tecnico:list"))


class TarefaReabrirView(TarefaConclusaoBaseView):
    """Reabre a tarefa limpando a data de conclusão existente."""

    def processar(self, tarefa: TarefaTecnica) -> None:
        tarefa.concluido_em = None
        tarefa.save(update_fields=["concluido_em", "atualizado_em"])
        messages.success(self.request, "Tarefa técnica reaberta.")


class TarefaExcluirView(TarefaConclusaoBaseView):
    """Exclui a tarefa diretamente da listagem para manter o backlog enxuto."""

    def processar(self, tarefa: TarefaTecnica) -> None:
        tarefa.delete()
        messages.success(self.request, "Tarefa técnica excluída.")


class TarefaCodexExecutarView(TarefaOwnershipMixin, View):
    """Enfileira a tarefa imediatamente para processamento em background pelo Codex."""

    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def post(self, request, *args, **kwargs):
        tarefa = get_object_or_404(TarefaTecnica, pk=self.kwargs["pk"])
        self._validar_acesso_objeto(tarefa)
        enfileirar_execucao(tarefa, request.user)
        messages.success(request, f"Tarefa #{tarefa.pk} enviada para a fila do Codex.")
        return HttpResponseRedirect(reverse("todo_tecnico:list"))


class TarefaCodexAgendarView(TarefaOwnershipMixin, View):
    """Agenda a execução da tarefa para um horário futuro com o mesmo backend da fila."""

    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def post(self, request, *args, **kwargs):
        tarefa = get_object_or_404(TarefaTecnica, pk=self.kwargs["pk"])
        self._validar_acesso_objeto(tarefa)
        form = CodexAgendamentoForm(request.POST)
        if not form.is_valid():
            for erro in form.errors.get("agendado_para", []):
                messages.error(request, erro)
            return HttpResponseRedirect(reverse("todo_tecnico:list"))

        enfileirar_execucao(tarefa, request.user, agendado_para=form.cleaned_data["agendado_para"])
        messages.success(request, f"Tarefa #{tarefa.pk} agendada para execução automática do Codex.")
        return HttpResponseRedirect(reverse("todo_tecnico:list"))


class CodexConfiguracaoUpdateView(TodoTecnicoMixin, View):
    """Atualiza a configuração reaproveitada por todas as execuções automáticas do módulo."""

    acl_nivel_minimo = RegraAcesso.NIVEL_MODIFICACAO

    def post(self, request, *args, **kwargs):
        configuracao = get_codex_configuracao()
        form = CodexConfiguracaoForm(request.POST, instance=configuracao)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração do Codex atualizada.")
        else:
            for _, erros in form.errors.items():
                for erro in erros:
                    messages.error(request, erro)
        return HttpResponseRedirect(reverse("todo_tecnico:list"))
