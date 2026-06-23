# Criado por José Eduardo Santana Martins em 04/06/2026
# Reúne formulários de LDAP e perfis de usuário, com validações de cadastro
# obrigatório e integração com setores.
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from setores.forms import setor_usuario_choices
from setores.models import SetorNode
from setores.services import ensure_user_primary_setor, primary_setor_for_user

from .models import ANDAR_CHOICES, BLOCO_CHOICES, LDAPDirectory, UsuarioPerfil


User = get_user_model()
BOOTSTRAP_INPUT = "form-control form-control-lg"
FOTO_EXTENSOES_PERMITIDAS = {"png", "jpeg", "jpg"}


class BootstrapFormMixin:
    """Aplica classes Bootstrap conforme o tipo de widget renderizado."""

    def _bootstrap_fields(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(field.widget, forms.RadioSelect):
                css = "spi-radio-group"
            elif isinstance(field.widget, forms.Select):
                css = "form-select form-select-lg"
            elif isinstance(field.widget, forms.Textarea):
                css = "form-control"
            else:
                css = BOOTSTRAP_INPUT
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css}".strip()


class LDAPDirectoryForm(BootstrapFormMixin, forms.ModelForm):
    """Formulário administrativo para cadastrar e testar diretórios LDAP."""

    class Meta:
        model = LDAPDirectory
        fields = ["nome", "host", "port", "use_ssl", "base_dn", "bind_dn", "bind_password", "ativo"]
        widgets = {"bind_password": forms.PasswordInput(render_value=True)}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bootstrap_fields()


class UsuarioPerfilForm(BootstrapFormMixin, forms.ModelForm):
    """Edita perfil existente e sincroniza e-mail, setor e papel administrativo."""

    login = forms.CharField(label="Login", required=False, disabled=True)
    email = forms.EmailField(label="E-mail", required=True)
    administrador_sistema = forms.BooleanField(label="Administrador do Sistema", required=False)

    class Meta:
        model = UsuarioPerfil
        fields = [
            "nome_completo",
            "foto",
            "email",
            "ramal",
            "celular",
            "cargo",
            "setor",
            "andar",
            "bloco",
            "data_nascimento",
        ]
        labels = {
            "celular": "Celular (Opcional)",
            "data_nascimento": "Data de nascimento (Opcional)",
        }
        widgets = {
            "andar": forms.Select(choices=[("", "Selecione")] + ANDAR_CHOICES),
            "bloco": forms.RadioSelect(choices=BLOCO_CHOICES),
            "data_nascimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


    def __init__(self, *args, current_user=None, **kwargs):
        self.current_user = current_user
        super().__init__(*args, **kwargs)
        self._bootstrap_fields()
        # Setor é apresentado como combobox alimentado pela árvore ativa de setores.
        self.fields["foto"].help_text = "Envie uma imagem PNG, JPEG ou JPG."
        self.fields["foto"].widget.attrs["accept"] = ".png,.jpeg,.jpg,image/png,image/jpeg"
        self.fields["andar"].choices = [("", "Selecione")] + ANDAR_CHOICES
        self.fields["bloco"].choices = BLOCO_CHOICES
        self.fields["setor"] = forms.ChoiceField(
            label="Setor",
            required=True,
            choices=setor_usuario_choices(self.instance),
            widget=forms.Select(attrs={"class": "form-select form-select-lg"}),
        )
        for field_name in ("nome_completo", "email", "ramal", "cargo", "setor", "andar", "bloco"):
            self.fields[field_name].required = True
        self.fields["foto"].required = not bool(self.instance and self.instance.foto)
        self.fields["login"].initial = self.instance.user.username
        self.fields["email"].initial = self.instance.user.email
        self.fields["administrador_sistema"].initial = self.instance.user.is_superuser
        if not (current_user and current_user.is_superuser):
            # Usuários comuns atualizam o próprio cadastro, mas não alteram privilégios.
            self.fields.pop("administrador_sistema")
        setor_atual = primary_setor_for_user(self.instance.user) if self.instance and self.instance.user_id else None
        if not self.is_bound:
            val = str(setor_atual.pk) if setor_atual else ""
            self.fields["setor"].initial = val
            self.initial["setor"] = val

    def clean_foto(self):
        """Garante foto no primeiro cadastro e limita formatos aceitos."""

        foto = self.cleaned_data.get("foto")
        if not foto and not (self.instance and self.instance.foto):
            raise ValidationError("A foto e obrigatoria no primeiro cadastro.")
        if foto:
            extensao = foto.name.rsplit(".", 1)[-1].lower() if "." in foto.name else ""
            if extensao not in FOTO_EXTENSOES_PERMITIDAS:
                raise ValidationError("Envie uma imagem PNG, JPEG ou JPG.")
        return foto

    def save(self, commit=True):
        perfil = super().save(commit=False)
        perfil.user.email = self.cleaned_data["email"]
        setor_id = self.cleaned_data["setor"]
        if commit:
            # O texto legado de setor é recalculado pelo serviço de vínculo com SetorNode.
            perfil.ultimo_recadastro_em = timezone.now()
            perfil.setor = ""
            perfil.save()
            perfil.user.save(update_fields=["email"])
            if setor_id:
                setor = SetorNode.objects.select_related("group").get(pk=setor_id)
                ensure_user_primary_setor(perfil.user, setor)
            if "administrador_sistema" in self.cleaned_data:
                is_admin = self.cleaned_data["administrador_sistema"]
                user = perfil.user
                if user.is_superuser != is_admin or user.is_staff != is_admin:
                    user.is_superuser = is_admin
                    user.is_staff = is_admin
                    user.save(update_fields=["is_superuser", "is_staff"])
        return perfil


class UsuarioCreateForm(BootstrapFormMixin, forms.ModelForm):
    """Cria usuário local, perfil obrigatório e vínculo inicial de setor."""

    login = forms.CharField(label="Login", max_length=150)
    email = forms.EmailField(label="E-mail", required=True)
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmar senha", widget=forms.PasswordInput)
    administrador_sistema = forms.BooleanField(label="Administrador do Sistema", required=False)

    class Meta:
        model = UsuarioPerfil
        fields = [
            "nome_completo",
            "foto",
            "email",
            "ramal",
            "celular",
            "cargo",
            "setor",
            "andar",
            "bloco",
            "data_nascimento",
        ]
        labels = {
            "celular": "Celular (Opcional)",
            "data_nascimento": "Data de nascimento (Opcional)",
        }
        widgets = {
            "andar": forms.Select(choices=[("", "Selecione")] + ANDAR_CHOICES),
            "bloco": forms.RadioSelect(choices=BLOCO_CHOICES),
            "data_nascimento": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        }


    def __init__(self, *args, current_user=None, **kwargs):
        self.current_user = current_user
        super().__init__(*args, **kwargs)
        self._bootstrap_fields()
        # O formulário de criação exige os mesmos dados que liberam o usuário após login.
        self.fields["foto"].help_text = "Envie uma imagem PNG, JPEG ou JPG."
        self.fields["foto"].widget.attrs["accept"] = ".png,.jpeg,.jpg,image/png,image/jpeg"
        self.fields["andar"].choices = [("", "Selecione")] + ANDAR_CHOICES
        self.fields["bloco"].choices = BLOCO_CHOICES
        self.fields["setor"] = forms.ChoiceField(
            label="Setor",
            required=True,
            choices=setor_usuario_choices(),
            widget=forms.Select(attrs={"class": "form-select form-select-lg"}),
        )
        for field_name in ("login", "nome_completo", "email", "ramal", "cargo", "setor", "andar", "bloco", "password1", "password2"):
            self.fields[field_name].required = True
        self.fields["foto"].required = True
        if not (current_user and current_user.is_superuser):
            self.fields.pop("administrador_sistema")

    def clean_login(self):
        """Bloqueia login duplicado sem depender de diferença entre maiúsculas/minúsculas."""

        username = (self.cleaned_data.get("login") or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Ja existe um usuario com este login.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        # A validação manual mantém as duas senhas no mesmo formulário de perfil.
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "As senhas nao coincidem.")
        return cleaned_data

    def clean_foto(self):
        """Obrigatoriedade e extensão da foto no primeiro cadastro local."""

        foto = self.cleaned_data.get("foto")
        if not foto:
            raise ValidationError("A foto e obrigatoria no primeiro cadastro.")
        extensao = foto.name.rsplit(".", 1)[-1].lower() if "." in foto.name else ""
        if extensao not in FOTO_EXTENSOES_PERMITIDAS:
            raise ValidationError("Envie uma imagem PNG, JPEG ou JPG.")
        return foto

    def save(self, commit=True):
        # Cria o User primeiro para que o signal gere o UsuarioPerfil associado.
        user = User(
            username=self.cleaned_data["login"],
            email=self.cleaned_data["email"],
            is_active=True,
        )
        is_admin = bool(self.cleaned_data.get("administrador_sistema"))
        user.is_superuser = is_admin
        user.is_staff = is_admin
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            perfil = user.perfil
            for field_name in ("nome_completo", "foto", "ramal", "celular", "cargo", "andar", "bloco", "data_nascimento"):
                val = self.cleaned_data.get(field_name)
                if val is None:
                    val = None if field_name == "data_nascimento" else ""
                setattr(perfil, field_name, val)
            perfil.setor = ""
            perfil.ultimo_recadastro_em = timezone.now()
            perfil.save()
            if self.cleaned_data.get("setor"):
                # A associação com setor também adiciona o usuário ao grupo Django do setor.
                setor = SetorNode.objects.select_related("group").get(pk=self.cleaned_data["setor"])
                ensure_user_primary_setor(user, setor)
            self.instance = perfil
            return perfil

        perfil = UsuarioPerfil(user=user)
        for field_name in ("nome_completo", "foto", "ramal", "celular", "cargo", "andar", "bloco", "data_nascimento"):
            val = self.cleaned_data.get(field_name)
            if val is None:
                val = None if field_name == "data_nascimento" else ""
            setattr(perfil, field_name, val)
        return perfil


class UsuarioSearchForm(forms.Form):
    """Campo simples de busca para telas que filtram perfis."""

    q = forms.CharField(required=False)


def user_search_queryset(queryset, term):
    """Aplica busca textual nas colunas exibidas nas listagens de usuários."""

    term = (term or "").strip()
    if not term:
        return queryset
    return queryset.filter(
        Q(nome_completo__icontains=term)
        | Q(ramal__icontains=term)
        | Q(cargo__icontains=term)
        | Q(setor__icontains=term)
        | Q(andar__icontains=term)
        | Q(bloco__icontains=term)
        | Q(user__email__icontains=term)
        | Q(user__username__icontains=term)
    )
