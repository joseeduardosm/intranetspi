# Criado por José Eduardo Santana Martins em 04/06/2026
# Define diretórios LDAP e perfis complementares dos usuários, incluindo
# dados obrigatórios para ramais e recadastro periódico.
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


ANDAR_CHOICES = [("Terreo", "Térreo")] + [(str(numero), str(numero)) for numero in range(1, 13)]
BLOCO_CHOICES = [("A", "A"), ("B", "B")]


class LDAPDirectory(models.Model):
    """Configuração de diretório LDAP usada pelo backend de autenticação."""

    nome = models.CharField("Nome", max_length=120)
    host = models.CharField("Servidor", max_length=255)
    port = models.PositiveIntegerField("Porta", default=389)
    use_ssl = models.BooleanField("Usar SSL", default=False)
    base_dn = models.CharField("Base DN", max_length=255)
    bind_dn = models.CharField("Usuario bind", max_length=255)
    bind_password = models.CharField("Senha bind", max_length=255)
    ativo = models.BooleanField("Ativo", default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome", "id"]
        verbose_name = "Diretorio LDAP"
        verbose_name_plural = "Diretorios LDAP"

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        if self.ativo:
            # Apenas um diretório ativo evita ambiguidade na autenticação corporativa.
            queryset = LDAPDirectory.objects.filter(ativo=True)
            if self.pk:
                queryset = queryset.exclude(pk=self.pk)
            if queryset.exists():
                raise ValidationError({"ativo": "Ja existe outro diretorio LDAP ativo."})


class UsuarioPerfil(models.Model):
    """Dados cadastrais e de contato associados a um usuário do Django."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    superior_imediato = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="liderados_imediatos",
        verbose_name="Superior imediato",
    )
    nome_completo = models.CharField("Nome completo", max_length=220, blank=True)
    foto = models.ImageField("Foto", upload_to="usuarios/fotos/", blank=True, null=True)
    ramal = models.CharField("Ramal", max_length=40, blank=True)
    celular = models.CharField("Celular", max_length=40, blank=True)
    cargo = models.CharField("Cargo", max_length=180, blank=True)
    setor = models.CharField("Setor", max_length=180, blank=True)
    andar = models.CharField("Andar", max_length=60, choices=ANDAR_CHOICES, blank=True)
    bloco = models.CharField("Bloco", max_length=60, choices=BLOCO_CHOICES, blank=True)
    data_nascimento = models.DateField("Data de nascimento", null=True, blank=True)
    ultimo_recadastro_em = models.DateTimeField("Ultimo recadastro", null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome_completo", "user__username"]
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfis de usuarios"

    def __str__(self):
        return self.nome_completo or self.user.username

    @property
    def whatsapp_url(self):
        """Normaliza o celular para link direto do WhatsApp quando possível."""

        if not self.celular:
            return ""
        digits = "".join(c for c in self.celular if c.isdigit())
        if len(digits) in (10, 11) and not digits.startswith("55"):
            digits = "55" + digits
        return f"https://wa.me/{digits}"

    @property
    def possui_campos_obrigatorios(self):
        """Indica se o perfil atende ao mínimo exigido para liberar navegação."""

        return bool((self.user.email or "").strip()) and bool(self.foto) and all(
            (getattr(self, field) or "").strip()
            for field in ("nome_completo", "ramal", "cargo", "setor", "andar", "bloco")
        )

    @property
    def precisa_recadastro(self):
        """Exige primeiro cadastro completo e revalidação a cada 30 dias."""

        if not self.possui_campos_obrigatorios:
            return True
        if not self.ultimo_recadastro_em:
            return True
        return (timezone.now() - self.ultimo_recadastro_em).days >= 30

    @property
    def andar_bloco_display(self):
        """Formata localização física para cartões de ramais e modais de contato."""

        andar_value = (self.andar or "").strip()
        bloco_value = (self.bloco or "").strip()
        if andar_value == "Terreo":
            andar = "Térreo"
        elif "andar" in andar_value.lower():
            andar = andar_value
        elif andar_value:
            andar = f"{andar_value} Andar"
        else:
            andar = ""

        if bloco_value.lower().startswith("bloco"):
            bloco = bloco_value
        elif bloco_value:
            bloco = f"Bloco {bloco_value}"
        else:
            bloco = ""

        if andar and bloco:
            return f"{andar} - {bloco}"
        return andar or bloco
