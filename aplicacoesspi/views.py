from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView, RedirectView


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
    return redirect('noticias:public_list')


class RootRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy('noticias:public_list')


class HomeView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        return reverse_lazy('noticias:public_list')
