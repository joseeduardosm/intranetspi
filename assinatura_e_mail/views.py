# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Controlar o formulário, a prévia e o download da assinatura de e-mail.

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse
from django.views.generic import FormView, View

from .forms import AssinaturaEmailForm
from .services import png_data_uri, render_signature_png


class AssinaturaEmailView(LoginRequiredMixin, FormView):
    """Exibe o formulário e gera a prévia PNG da assinatura institucional."""

    template_name = 'assinatura_e_mail/form.html'
    form_class = AssinaturaEmailForm

    def get_initial(self):
        # Usa o perfil do usuário para reduzir retrabalho no preenchimento do formulário.
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
        
        # Persiste campos opcionais que também pertencem ao perfil do usuário.
        try:
            perfil = self.request.user.perfil
            perfil.celular = payload.get('celular') or ''
            perfil.data_nascimento = payload.get('data_nascimento')
            perfil.save()
        except ObjectDoesNotExist:
            pass

        # O token assinado permite baixar a imagem sem armazenar o payload em sessão ou banco.
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
    """Valida o token temporário e entrega a assinatura gerada como arquivo PNG."""

    def get(self, request):
        token = request.GET.get('token', '')
        if not token:
            raise Http404('Assinatura nao encontrada.')
        try:
            payload = signing.loads(token, max_age=3600)
        except signing.BadSignature as exc:
            raise Http404('Assinatura invalida.') from exc

        # Recria a imagem a partir do payload assinado para garantir consistência no download.
        png_bytes = render_signature_png(payload)
        response = HttpResponse(png_bytes, content_type='image/png')
        response['Content-Disposition'] = 'attachment; filename=\"assinatura-email.png\"'
        return response
