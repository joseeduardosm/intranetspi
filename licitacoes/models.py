from django.conf import settings
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
    usa_editor_dinamico = models.BooleanField(default=False)

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
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etps_tic_atualizados',
    )

    class Meta:
        ordering = ['-atualizado_em', '-id']

    def __str__(self):
        return self.nome


class SessaoEtpTic(models.Model):
    etp = models.ForeignKey(EtpTic, on_delete=models.CASCADE, related_name='sessoes')
    titulo = models.CharField(max_length=300)
    ordem = models.PositiveIntegerField(default=1)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.ordem}. {self.titulo}'


class ItemEtpTic(models.Model):
    class Tipo(models.TextChoices):
        NUMERICO = 'NUMERICO', 'Item/Subitem'
        SUBSECAO = 'SUBSECAO', 'Subsecao'
        INCISO = 'INCISO', 'Inciso'
        ALINEA = 'ALINEA', 'Alinea'

    sessao = models.ForeignKey(SessaoEtpTic, on_delete=models.CASCADE, related_name='itens')
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


class Dfd(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        CONCLUIDO = 'CONCLUIDO', 'Concluido'

    OBJETO_NAO_LUXO_PADRAO = (
        '1.2. O objeto desta contratação não se enquadra como sendo de bem de luxo, '
        'conforme Decreto nº 67.985, de 27 de setembro de 2023.'
    )

    nome = models.CharField(max_length=180)
    numero_processo = models.CharField('Numero do processo', max_length=120)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RASCUNHO)
    secao_atual = models.PositiveIntegerField(default=1)

    informacoes_preliminares = models.TextField(blank=True)
    descricao_objeto = models.TextField(blank=True)
    objeto_nao_luxo = models.TextField('Item 1.2', default=OBJETO_NAO_LUXO_PADRAO, blank=True)
    justificativa_necessidade = models.TextField(blank=True)
    estimativa_quantidade_valores = models.TextField(blank=True)
    vinculacao_outro_dfd = models.TextField(blank=True)
    responsaveis = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em', '-id']

    def __str__(self):
        return self.nome


class DfdItemTabela(models.Model):
    dfd = models.ForeignKey(Dfd, on_delete=models.CASCADE, related_name='itens_tabela')
    ordem = models.PositiveIntegerField(default=1)
    especificacao = models.TextField('Especificacao')
    catmat = models.CharField('CATMAT', max_length=120, blank=True)
    siafisico = models.CharField('SIAFISICO', max_length=120, blank=True)
    unidade_medida = models.CharField('Unidade de medida', max_length=120, blank=True)
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=2)
    valor_unitario = models.DecimalField('Valor unitario', max_digits=14, decimal_places=2)
    valor_total = models.DecimalField('Valor total', max_digits=14, decimal_places=2)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.ordem} - {self.especificacao[:60]}'


class TermoReferencia(models.Model):
    nome = models.CharField(max_length=180)
    numero_processo = models.CharField('Numero do processo', max_length=120)
    link = models.URLField('Link do processo', max_length=500, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='termos_referencia_atualizados',
    )

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
        SUBSECAO = 'SUBSECAO', 'Subsecao'

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


class TabelaItemLinha(models.Model):
    item = models.ForeignKey(ItemTR, on_delete=models.CASCADE, related_name='tabela_linhas')
    ordem = models.PositiveIntegerField(default=1)
    descricao = models.TextField('Descricao')
    catmat_catser = models.CharField('CATMAT/CATSER', max_length=120, blank=True)
    siafisico = models.CharField('Siafisico', max_length=120, blank=True)
    unidade_fornecimento = models.CharField('Unidade de Fornecimento', max_length=120, blank=True)
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=2)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'{self.ordem} - {self.descricao[:60]}'

# Create your models here.
