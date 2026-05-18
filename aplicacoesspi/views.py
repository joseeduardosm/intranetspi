from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, RedirectView, TemplateView


class SuperuserLoginView(FormView):
    template_name = 'registration/login.html'
    form_class = AuthenticationForm
    success_url = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_superuser:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        user = form.get_user()
        if not user.is_superuser:
            messages.error(self.request, 'Acesso permitido somente para superusuários.')
            return self.form_invalid(form)
        login(self.request, user)
        return redirect(self.get_success_url())


def logout_view(request):
    logout(request)
    return redirect('login')


class RootRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated and self.request.user.is_superuser:
            return reverse_lazy('home')
        return reverse_lazy('login')


class HomeView(LoginRequiredMixin, TemplateView):
    template_name = 'home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.is_superuser:
            logout(request)
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)
