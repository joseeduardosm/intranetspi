from django.db import models


class EtpTic(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        CONCLUIDO = 'CONCLUIDO', 'Concluido'

    DECLARACAO_PADRAO = 'Esta equipe de planejamento declara viavel esta contratacao.'

    nome = models.CharField(max_length=180)
    numero_processo = models.CharField('Numero do processo', max_length=120)
    link = models.URLField('Link do processo', max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO)
    secao_atual = models.PositiveIntegerField(default=1)

    descricao_necessidade = models.TextField(blank=True)
    area_requisitante = models.CharField(max_length=180, blank=True)
    responsavel_area = models.CharField(max_length=180, blank=True)
    necessidades_negocio = models.TextField(blank=True)
    necessidades_tecnologicas = models.TextField(blank=True)
    demais_requisitos = models.TextField(blank=True)
    estimativa_demanda = models.TextField(blank=True)
    levantamento_solucoes = models.TextField(blank=True)
    analise_comparativa_solucoes = models.TextField(blank=True)
    solucoes_inviaveis = models.TextField(blank=True)
    analise_comparativa_custos_tco = models.TextField(blank=True)
    descricao_solucao_tic = models.TextField(blank=True)
    estimativa_custo_valor = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    estimativa_custo_texto = models.TextField(blank=True)
    justificativa_tecnica = models.TextField(blank=True)
    justificativa_economica = models.TextField(blank=True)
    beneficios_contratacao = models.TextField(blank=True)
    providencias_adotadas = models.TextField(blank=True)
    declaracao_viabilidade = models.TextField(default=DECLARACAO_PADRAO)
    justificativa_viabilidade = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em', '-id']

    def __str__(self):
        return self.nome


class TermoReferencia(models.Model):
    nome = models.CharField(max_length=180)
    numero_processo = models.CharField('Numero do processo', max_length=120)
    link = models.URLField('Link do processo', max_length=500, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome', 'id']

    def __str__(self):
        return f'{self.nome} ({self.numero_processo})'


class SessaoTR(models.Model):
    termo = models.ForeignKey(TermoReferencia, on_delete=models.CASCADE, related_name='sessoes')
    titulo = models.CharField(max_length=300)
    ordem = models.PositiveIntegerField(default=1)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.ordem}. {self.titulo}'


class ItemTR(models.Model):
    class Tipo(models.TextChoices):
        NUMERICO = 'NUMERICO', 'Item/Subitem'
        INCISO = 'INCISO', 'Inciso'
        ALINEA = 'ALINEA', 'Alinea'

    sessao = models.ForeignKey(SessaoTR, on_delete=models.CASCADE, related_name='itens')
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='filhos',
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.NUMERICO)
    texto = models.TextField()
    ordem = models.PositiveIntegerField(default=1)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return self.texto[:80]

# Create your models here.
