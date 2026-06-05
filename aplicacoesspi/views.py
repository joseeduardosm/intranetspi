from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import FormView, RedirectView

from usuarios.services import is_system_user


class SuperuserLoginView(FormView):
    template_name = 'registration/login.html'
    form_class = AuthenticationForm
    success_url = reverse_lazy('root')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('root')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return redirect(self.get_success_url())


def logout_view(request):
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
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy('noticias:public_list')


class HomeView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy('root')


def permission_denied_view(request, exception=None):
    return render(request, 'errors/403.html', status=403)

