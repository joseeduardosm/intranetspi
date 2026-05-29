from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import LDAPDirectoryForm, UsuarioCreateForm, UsuarioPerfilForm, user_search_queryset
from .models import LDAPDirectory, UsuarioPerfil
from .services import SYSTEM_USERNAMES, build_ldap_server, ensure_usuario_perfil


SORT_FIELDS = {
    "nome": "nome_completo",
    "email": "user__email",
    "ramal": "ramal",
    "cargo": "cargo",
    "setor": "setor",
    "andar": "andar",
    "bloco": "bloco",
}


def _sort_params(request):
    sort = request.GET.get("sort", "nome").strip().lower()
    direction = request.GET.get("dir", "asc").strip().lower()
    if sort not in SORT_FIELDS:
        sort = "nome"
    if direction not in {"asc", "desc"}:
        direction = "asc"
    return sort, direction


def _sort_links(request):
    term = request.GET.get("q", "").strip()
    current_sort, current_dir = _sort_params(request)
    links = {}
    for key in SORT_FIELDS:
        next_dir = "desc" if current_sort == key and current_dir == "asc" else "asc"
        params = []
        if term:
            params.append(f"q={term}")
        params.append(f"sort={key}")
        params.append(f"dir={next_dir}")
        links[key] = "&".join(params)
    return links


def _test_ldap_connection(config):
    try:
        from ldap3 import Connection, NONE, Server, Tls
        from ldap3.core.exceptions import LDAPException
    except Exception:
        return "error", "Biblioteca ldap3 nao encontrada."

    server = build_ldap_server(config, Server, NONE, Tls)
    try:
        connection = Connection(
            server,
            user=config.bind_dn,
            password=config.bind_password,
            auto_bind=True,
        )
        connection.unbind()
        return "success", "Conexao estabelecida com sucesso."
    except (LDAPException, OSError) as exc:
        detalhe = str(exc).strip() or exc.__class__.__name__
        return "error", f"Falha ao conectar no diretorio LDAP: {detalhe}"


class AuthenticatedListMixin(LoginRequiredMixin, ListView):
    paginate_by = 20
    context_object_name = "perfis"
    template_name = "usuarios/list.html"

    page_title = ""
    page_description = ""
    show_delete = False

    def get_queryset(self):
        queryset = UsuarioPerfil.objects.select_related("user").exclude(user__username__in=SYSTEM_USERNAMES)
        queryset = user_search_queryset(queryset, self.request.GET.get("q"))
        sort, direction = _sort_params(self.request)
        ordering = SORT_FIELDS[sort]
        if direction == "desc":
            ordering = f"-{ordering}"
        return queryset.order_by(ordering, "user__username")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort, direction = _sort_params(self.request)
        context.update(
            {
                "titulo": self.page_title,
                "descricao": self.page_description,
                "show_delete": self.show_delete,
                "q": self.request.GET.get("q", "").strip(),
                "sort_links": _sort_links(self.request),
                "current_sort": sort,
                "current_dir": direction,
            }
        )
        return context


class RamaisListView(AuthenticatedListMixin):
    paginate_by = 8
    page_title = "Ramais"
    page_description = "Diretorio interno de usuarios."
    template_name = "usuarios/ramais.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        for field_name in ("nome_completo", "ramal", "cargo", "setor", "andar", "bloco"):
            queryset = queryset.exclude(**{field_name: ""})
        return queryset.exclude(foto="").exclude(foto__isnull=True).exclude(user__email="")


class UsuariosListView(AuthenticatedListMixin):
    paginate_by = 10
    page_title = "Usuarios"
    page_description = "Gestao de usuarios do sistema."
    show_delete = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["show_create"] = self.request.user.is_superuser
        params = self.request.GET.copy()
        params.pop("page", None)
        context["pagination_query"] = params.urlencode()
        return context


class UsuarioPerfilCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = UsuarioPerfil
    form_class = UsuarioCreateForm
    template_name = "usuarios/form.html"

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        return reverse("usuarios:list")

    def form_valid(self, form):
        messages.success(self.request, "Usuario criado.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Novo usuario"
        context["voltar_url"] = reverse("usuarios:list")
        context["is_create"] = True
        return context


class UsuarioPerfilUpdateView(LoginRequiredMixin, UpdateView):
    model = UsuarioPerfil
    form_class = UsuarioPerfilForm
    template_name = "usuarios/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(UsuarioPerfil.objects.select_related("user"), pk=kwargs["pk"])
        if not self._can_edit(request.user, self.object):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _can_edit(self, user, perfil):
        return user.is_authenticated and (user.is_superuser or perfil.user_id == user.id)

    def get_object(self, queryset=None):
        return self.object

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["current_user"] = self.request.user
        return kwargs

    def get_success_url(self):
        if self.request.user.id == self.object.user_id:
            return reverse("usuarios:ramais")
        return reverse("usuarios:list")

    def form_valid(self, form):
        messages.success(self.request, "Cadastro atualizado.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Editar usuario"
        context["voltar_url"] = reverse("usuarios:list")
        context["is_create"] = False
        return context


class UsuarioPerfilDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = UsuarioPerfil
    template_name = "usuarios/confirm_delete.html"
    success_url = reverse_lazy("usuarios:list")

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser

    def form_valid(self, form):
        user = self.object.user
        messages.success(self.request, "Usuario excluido.")
        response = super().form_valid(form)
        user.delete()
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Excluir usuario"
        context["descricao"] = f'Confirma a exclusao de "{self.object}"?'
        return context


class LDAPAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_superuser


class LDAPDirectoryListView(LDAPAdminMixin, ListView):
    model = LDAPDirectory
    template_name = "usuarios/ldap_directory_list.html"
    context_object_name = "directories"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Diretorios LDAP"
        return context


class LDAPDirectoryCreateView(LDAPAdminMixin, View):
    template_name = "usuarios/ldap_directory_form.html"

    def get(self, request):
        form = LDAPDirectoryForm()
        return render(request, self.template_name, {"form": form, "titulo": "Novo diretorio LDAP"})

    def post(self, request):
        form = LDAPDirectoryForm(request.POST)
        feedback = None
        if form.is_valid():
            if "test" in request.POST:
                level, message = _test_ldap_connection(form.save(commit=False))
                feedback = (level, message)
            else:
                form.save()
                messages.success(request, "Diretorio LDAP criado.")
                return redirect("usuarios:ldap_list")
        else:
            feedback = ("error", "Corrija os erros do formulario.")
        return render(request, self.template_name, {"form": form, "titulo": "Novo diretorio LDAP", "feedback": feedback})


class LDAPDirectoryUpdateView(LDAPAdminMixin, View):
    template_name = "usuarios/ldap_directory_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = get_object_or_404(LDAPDirectory, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        form = LDAPDirectoryForm(instance=self.object)
        return render(request, self.template_name, {"form": form, "titulo": "Editar diretorio LDAP", "object": self.object})

    def post(self, request, pk):
        form = LDAPDirectoryForm(request.POST, instance=self.object)
        feedback = None
        if form.is_valid():
            if "test" in request.POST:
                level, message = _test_ldap_connection(form.save(commit=False))
                feedback = (level, message)
            else:
                form.save()
                messages.success(request, "Diretorio LDAP atualizado.")
                return redirect("usuarios:ldap_list")
        else:
            feedback = ("error", "Corrija os erros do formulario.")
        return render(
            request,
            self.template_name,
            {"form": form, "titulo": "Editar diretorio LDAP", "object": self.object, "feedback": feedback},
        )


class LDAPDirectoryDeleteView(LDAPAdminMixin, DeleteView):
    model = LDAPDirectory
    template_name = "usuarios/confirm_delete.html"
    success_url = reverse_lazy("usuarios:ldap_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["titulo"] = "Excluir diretorio LDAP"
        context["descricao"] = f'Confirma a exclusao de "{self.object.nome}"?'
        return context
