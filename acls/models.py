# Criado por José Eduardo Santana Martins em 04/06/2026

from django.db import models
from django.contrib.auth.models import Group
from django.conf import settings


class Recurso(models.Model):
    """Representa cada app ou área funcional que pode ser protegida por ACL."""

    nome = models.CharField("Nome do App/Recurso", max_length=100, unique=True)
    slug = models.SlugField("Slug identificador", max_length=100, unique=True, help_text="Nome da pasta do app (ex: 'licitacoes')")
    descricao = models.TextField("Descrição", blank=True)
    url_base = models.CharField("URL base", max_length=160, blank=True, help_text="Opcional. Quando preenchida, substitui a URL derivada do slug.")

    class Meta:
        verbose_name = "App/Recurso Protegido"
        verbose_name_plural = "Apps/Recursos Protegidos"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.slug})"


class RegraAcesso(models.Model):
    """Define o nível de permissão aplicado a vários usuários e grupos em um recurso."""

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
    
    usuarios = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='regras_acesso',
        verbose_name="Usuários",
        help_text="Selecione zero ou vários usuários para aplicar a regra."
    )
    grupos = models.ManyToManyField(
        Group,
        blank=True,
        related_name='regras_acesso',
        verbose_name="Grupos/Setores",
        help_text="Selecione zero ou vários grupos/setores para aplicar a regra."
    )
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Regra de Acesso"
        verbose_name_plural = "Regras de Acesso"
        ordering = ["-id"]

    def __str__(self):
        # Monta uma descrição legível combinando o nível, o recurso e os alvos da regra.
        alvos = []
        if self.pk:
            usuarios = list(self.usuarios.all()[:3])
            grupos = list(self.grupos.all()[:3])
            if usuarios:
                nomes_usuarios = ", ".join(str(usuario) for usuario in usuarios)
                sufixo_usuarios = "..." if self.usuarios.count() > len(usuarios) else ""
                alvos.append(f"Usuários: {nomes_usuarios}{sufixo_usuarios}")
            if grupos:
                nomes_grupos = ", ".join(str(grupo) for grupo in grupos)
                sufixo_grupos = "..." if self.grupos.count() > len(grupos) else ""
                alvos.append(f"Grupos/Setores: {nomes_grupos}{sufixo_grupos}")

        if not alvos:
            alvos.append("Sem alvos definidos")

        return f"{self.get_nivel_display()} -> {self.recurso.nome} ({', '.join(alvos)})"

    def clean(self):
        from django.core.exceptions import ValidationError

        # Durante a validação de ModelForm, os relacionamentos muitos-para-muitos ainda
        # não ficam disponíveis na instância. Por isso, a validação principal permanece
        # no formulário, e aqui cobrimos chamadas diretas ao model já persistido.
        if self.pk and not self.usuarios.exists() and not self.grupos.exists():
            raise ValidationError("Você deve selecionar pelo menos um Usuário ou um Grupo/Setor.")
