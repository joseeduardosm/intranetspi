# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir o modelo de atalho e a validação de URLs internas ou externas.

from urllib.parse import urlparse

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models


def validar_url_interna_ou_externa(value):
    """Aceita caminhos internos iniciados por / ou URLs externas http/https completas."""

    normalized = (value or '').strip()
    if not normalized:
        raise ValidationError('Informe uma URL valida.')

    if normalized.startswith('/'):
        return

    parsed = urlparse(normalized)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValidationError('Informe uma URL interna iniciando com / ou externa com http:// ou https://.')


class Atalho(models.Model):
    """Representa um card/link configurável exibido próximo às notícias."""

    titulo = models.CharField('Titulo', max_length=120)
    imagem = models.ImageField(
        'Imagem',
        upload_to='atalhos/',
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg'])],
    )
    url = models.CharField(
        'URL',
        max_length=500,
        validators=[validar_url_interna_ou_externa],
    )
    ordem = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Atalho'
        verbose_name_plural = 'Atalhos'

    def __str__(self):
        # O título identifica o atalho nas telas administrativas e no admin do Django.
        return self.titulo
