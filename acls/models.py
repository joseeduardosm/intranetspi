from django.db import models
from django.contrib.auth.models import Group
from django.conf import settings

class Recurso(models.Model):
    nome = models.CharField("Nome do App/Recurso", max_length=100, unique=True)
    slug = models.SlugField("Slug identificador", max_length=100, unique=True, help_text="Nome da pasta do app (ex: 'licitacoes')")
    descricao = models.TextField("Descrição", blank=True)

    class Meta:
        verbose_name = "App/Recurso Protegido"
        verbose_name_plural = "Apps/Recursos Protegidos"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.slug})"


class RegraAcesso(models.Model):
    NIVEL_LEITURA = 'LEITURA'
    NIVEL_MODIFICACAO = 'MODIFICACAO'
    NIVEL_CONTROLE_TOTAL = 'CONTROLE_TOTAL'

    NIVEL_PERMISSAO = [
        (NIVEL_LEITURA, 'Leitura (Vê tudo)'),
        (NIVEL_MODIFICACAO, 'Modificação (Cria, vê e edita o próprio)'),
        (NIVEL_CONTROLE_TOTAL, 'Controle Total (Cria, vê e edita todos)'),
    ]

    recurso = models.ForeignKey(Recurso, on_delete=models.CASCADE, related_name='regras')
    nivel = models.CharField("Nível de Permissão", max_length=20, choices=NIVEL_PERMISSAO, default=NIVEL_LEITURA)
    
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='regras_acesso',
        verbose_name="Usuário",
        help_text="Selecione o usuário para aplicar a regra."
    )
    grupo = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='regras_acesso',
        verbose_name="Grupo/Setor",
        help_text="Selecione o grupo/setor para aplicar a regra."
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regra de Acesso"
        verbose_name_plural = "Regras de Acesso"
        ordering = ["-id"]

    def __str__(self):
        alvos = []
        if self.usuario:
            alvos.append(f"Usuário: {self.usuario}")
        if self.grupo:
            alvos.append(f"Grupo/Setor: {self.grupo}")
        return f"{self.get_nivel_display()} -> {self.recurso.nome} ({', '.join(alvos)})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.usuario and not self.grupo:
            raise ValidationError("Você deve selecionar pelo menos um Usuário ou um Grupo/Setor.")
