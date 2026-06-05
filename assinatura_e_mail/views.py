from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse
from django.views.generic import FormView, View

from .forms import AssinaturaEmailForm
from .services import png_data_uri, render_signature_png


class AssinaturaEmailView(LoginRequiredMixin, FormView):
    template_name = 'assinatura_e_mail/form.html'
    form_class = AssinaturaEmailForm

    def get_initial(self):
        initial = super().get_initial()
        try:
            perfil = self.request.user.perfil
        except ObjectDoesNotExist:
            perfil = None
        if perfil:
            initial['nome_completo'] = perfil.nome_completo
            initial['cargo_funcao'] = perfil.cargo
            initial['departamento'] = perfil.setor
            initial['ramal'] = perfil.ramal
            initial['celular'] = perfil.celular
            initial['data_nascimento'] = perfil.data_nascimento
        initial['email'] = self.request.user.email
        return initial

    def form_valid(self, form):
        payload = form.cleaned_data
        
        # Save optional fields to profile
        try:
            perfil = self.request.user.perfil
            perfil.celular = payload.get('celular') or ''
            perfil.data_nascimento = payload.get('data_nascimento')
            perfil.save()
        except ObjectDoesNotExist:
            pass

        token = signing.dumps(payload)
        png_bytes = render_signature_png(payload)
        context = self.get_context_data(
            form=form,
            preview_src=png_data_uri(png_bytes),
            download_token=token,
            gerado=True,
        )
        return self.render_to_response(context)



class AssinaturaEmailDownloadView(LoginRequiredMixin, View):
    def get(self, request):
        token = request.GET.get('token', '')
        if not token:
            raise Http404('Assinatura nao encontrada.')
        try:
            payload = signing.loads(token, max_age=3600)
        except signing.BadSignature as exc:
            raise Http404('Assinatura invalida.') from exc

        png_bytes = render_signature_png(payload)
        response = HttpResponse(png_bytes, content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename=\"assinatura-email.png\"'
        return response
