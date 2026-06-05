# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir os modelos de ETP TIC, DFD, TR, fornecedores e pesquisa de preço.

from django.conf import settings
from django.db import models


class EtpTic(models.Model):
    """Estudo Técnico Preliminar de TIC com seções legadas e editor dinâmico."""

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
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etps_tic_criados',
    )
    compartilhado_com = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='etps_tic_compartilhados',
    )
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
    """Seção customizada do editor dinâmico de um ETP TIC."""

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
    """Item hierárquico de uma seção do ETP TIC."""

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
    """Documento de Formalização de Demanda usado antes do TR."""

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
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dfds_criados',
    )
    compartilhado_com = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='dfds_compartilhados',
    )

    class Meta:
        ordering = ['-atualizado_em', '-id']

    def __str__(self):
        return self.nome


class DfdItemTabela(models.Model):
    """Linha da tabela de itens vinculada ao DFD."""

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
    """Termo de Referência com seções e itens editáveis em árvore."""

    nome = models.CharField(max_length=180)
    numero_processo = models.CharField('Numero do processo', max_length=120)
    link = models.URLField('Link do processo', max_length=500, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='termos_referencia_criados',
    )
    compartilhado_com = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='termos_referencia_compartilhados',
    )
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
    """Seção do Termo de Referência."""

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
    """Item hierárquico de uma seção do Termo de Referência."""

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
    """Linha de especificação e quantidade associada a um item do TR."""

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


class Fornecedor(models.Model):
    """Fornecedor cadastrado para cotações e pesquisas de preço."""

    razao_social = models.CharField('Razão Social', max_length=220)
    cnpj = models.CharField('CNPJ', max_length=20, unique=True)
    telefone = models.CharField('Telefone', max_length=60)
    contato = models.CharField('Contato', max_length=180)
    email_contato = models.CharField('E-mail do contato', max_length=500)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['razao_social', 'cnpj']

    def __str__(self):
        return self.razao_social


class PesquisaPreco(models.Model):
    """Pesquisa de preço vinculada a um Termo de Referência."""

    class Tipo(models.TextChoices):
        AQUISICAO = 'AQUISICAO', 'Aquisição'
        SERVICO = 'SERVICO', 'Serviço'

    termo = models.OneToOneField(TermoReferencia, on_delete=models.CASCADE, related_name='pesquisa_preco')
    tipo = models.CharField('Tipo', max_length=20, choices=Tipo.choices)
    pesquisador_nome = models.CharField('Nome do pesquisador', max_length=180, default='')
    pesquisador_email = models.EmailField('E-mail do pesquisador', default='')
    pesquisador_cargo = models.CharField('Cargo do pesquisador', max_length=180, default='')
    vigencia_meses = models.PositiveIntegerField('Vigência em meses', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-atualizado_em', '-id']

    def __str__(self):
        return f'Pesquisa de Preço - {self.termo}'


class PesquisaPrecoFornecedor(models.Model):
    """Participação de um fornecedor em uma pesquisa de preço."""

    pesquisa = models.ForeignKey(PesquisaPreco, on_delete=models.CASCADE, related_name='fornecedores_pesquisa')
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE, related_name='pesquisas_preco')
    data_resposta = models.DateField('Data da resposta', null=True, blank=True)
    validade_orcamento_dias = models.PositiveIntegerField('Validade do orçamento em dias', null=True, blank=True)
    documento_fornecedor = models.FileField('Documento do fornecedor', upload_to='licitacoes/pesquisa_preco/orcamentos/', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['fornecedor__razao_social', 'id']
        constraints = [
            models.UniqueConstraint(fields=['pesquisa', 'fornecedor'], name='uniq_fornecedor_por_pesquisa_preco'),
        ]

    def __str__(self):
        return f'{self.fornecedor} - {self.pesquisa}'


class PesquisaPrecoContato(models.Model):
    """Registro de contato realizado com um fornecedor da pesquisa."""

    pesquisa_fornecedor = models.ForeignKey(PesquisaPrecoFornecedor, on_delete=models.CASCADE, related_name='contatos')
    data_contato = models.DateField('Data do contato')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_contato', '-id']

    def __str__(self):
        return f'{self.pesquisa_fornecedor.fornecedor} em {self.data_contato:%d/%m/%Y}'


class PesquisaPrecoFornecedorNota(models.Model):
    """Anotação histórica sobre um fornecedor dentro da pesquisa."""

    pesquisa_fornecedor = models.ForeignKey(PesquisaPrecoFornecedor, on_delete=models.CASCADE, related_name='notas')
    texto = models.TextField('Nota')
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notas_pesquisa_preco',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']

    def __str__(self):
        return f'Nota de {self.pesquisa_fornecedor.fornecedor} em {self.criado_em:%d/%m/%Y %H:%M}'


class PesquisaPrecoItemValor(models.Model):
    """Valor unitário informado por fornecedor para um item do TR."""

    pesquisa_fornecedor = models.ForeignKey(PesquisaPrecoFornecedor, on_delete=models.CASCADE, related_name='valores')
    item = models.ForeignKey(TabelaItemLinha, on_delete=models.CASCADE, related_name='valores_pesquisa_preco')
    preco_unitario = models.DecimalField('Preço unitário', max_digits=14, decimal_places=2)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item__ordem', 'id']
        constraints = [
            models.UniqueConstraint(fields=['pesquisa_fornecedor', 'item'], name='uniq_preco_item_por_fornecedor'),
        ]

    def __str__(self):
        return f'{self.pesquisa_fornecedor.fornecedor} - item {self.item.ordem}'
