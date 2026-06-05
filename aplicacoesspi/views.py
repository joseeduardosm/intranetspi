# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Concentrar views globais de login, logout, redirecionamento inicial e erro 403.

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, RedirectView

from usuarios.services import is_system_user


class SuperuserLoginView(FormView):
    """Controla o login inicial e evita exibir o formulário para usuários autenticados."""

    template_name = 'registration/login.html'
    form_class = AuthenticationForm
    success_url = reverse_lazy('root')

    def dispatch(self, request, *args, **kwargs):
        # Usuários já autenticados são enviados ao fluxo inicial do portal.
        if request.user.is_authenticated:
            return redirect('root')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        # O AuthenticationForm precisa da requisição para validar credenciais e políticas de login.
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        # Autentica o usuário aprovado pelo formulário e segue para a rota de entrada.
        user = form.get_user()
        login(self.request, user)
        return redirect(self.get_success_url())


def logout_view(request):
    """Encerra a sessão e remove cadastros temporários incompletos quando necessário."""

    user = request.user if request.user.is_authenticated else None
    should_delete_user = False
    if user and not is_system_user(user):
        perfil = getattr(user, "perfil", None)
        should_delete_user = bool(
            perfil
            and not perfil.ultimo_recadastro_em
            and not perfil.possui_campos_obrigatorios
        )
    logout(request)
    if should_delete_user:
        user.delete()
    return redirect('noticias:public_list')


class RootRedirectView(RedirectView):
    """Direciona a raiz do projeto para a lista pública de notícias."""

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy('noticias:public_list')


class HomeView(RedirectView):
    """Mantém a rota histórica de home apontando para o fluxo raiz."""

    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy('root')


def permission_denied_view(request, exception=None):
    """Renderiza a página institucional de erro 403."""

    return render(request, 'errors/403.html', status=403)
