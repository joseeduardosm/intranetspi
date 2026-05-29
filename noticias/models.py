from django.core.exceptions import ValidationError
from django.db import models


class Noticia(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        AGENDADA = 'AGENDADA', 'Agendada'
        PUBLICADA = 'PUBLICADA', 'Publicada'

    imagem_destaque = models.ImageField('Imagem destaque', upload_to='noticias/destaques/')
    anexo_pdf = models.FileField('Anexo', upload_to='noticias/anexos/', blank=True)
    titulo = models.CharField('Titulo', max_length=220)
    texto_noticia = models.TextField('Texto da noticia')
    data_publicacao = models.DateTimeField('Data de publicacao', null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO)
    fixada = models.BooleanField('Fixada', default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fixada', '-data_publicacao', '-id']
        verbose_name = 'Noticia'
        verbose_name_plural = 'Noticias'

    def __str__(self):
        return self.titulo

    @property
    def anexo_nome(self):
        return self.anexo_pdf.name.rsplit('/', 1)[-1] if self.anexo_pdf else ''

    @property
    def anexo_e_pdf(self):
        return self.anexo_nome.lower().endswith('.pdf')

    def clean(self):
        super().clean()
        if self.status in {self.Status.AGENDADA, self.Status.PUBLICADA} and not self.data_publicacao:
            raise ValidationError({'data_publicacao': 'Informe a data de publicacao para noticias agendadas ou publicadas.'})
