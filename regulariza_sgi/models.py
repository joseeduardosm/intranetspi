# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir imóveis, processos SEI, anexos, ciclos e marcos processuais.

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from .services import ESTADOS


class Imovel(models.Model):
    """Cadastro principal do imóvel acompanhado pelo fluxo de regularização."""

    inscricao_imobiliaria = models.CharField('Inscrição imobiliária', max_length=120, unique=True)
    matricula = models.CharField('Matrícula', max_length=120)
    processo_judicial = models.CharField('Processo judicial de desapropriação', max_length=120)
    sei = models.CharField('SEI', max_length=120, blank=True)
    link_sei = models.URLField('Link SEI', max_length=500, blank=True)
    numero_sgi = models.CharField('Número SGI', max_length=120)
    uf = models.CharField('Estado', max_length=2, choices=ESTADOS, default='SP')
    municipio = models.CharField('Município', max_length=120)
    logradouro = models.CharField('Logradouro', max_length=255)
    bairro = models.CharField('Bairro', max_length=120)
    numero = models.CharField('Número', max_length=40)
    area = models.DecimalField('Área (m²)', max_digits=14, decimal_places=2, null=True, blank=True)
    motivo_desapropriacao = models.TextField('Motivo da desapropriação', blank=True)
    imissao_posse = models.DateField('Imissão na posse', null=True, blank=True)
    imunidade = models.BooleanField('Imunidade', default=False)
    tempo_imunidade = models.PositiveIntegerField('Tempo de imunidade (anos)', null=True, blank=True)
    exercicio_cobranca = models.CharField('Exercício da cobrança', max_length=120, blank=True)
    divida_ativa = models.CharField('Dívida ativa', max_length=180, blank=True)
    numero_divida = models.CharField('Nº da dívida', max_length=180, blank=True)
    dividas_nao_ajuizadas = models.DecimalField(
        'Dívidas não ajuizadas',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
    )
    dividas_ajuizadas = models.DecimalField(
        'Dívidas ajuizadas',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
    )
    encargos = models.DecimalField(
        'Encargos',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        default=None,
    )
    possui_cadin = models.BooleanField('Possui notificação CADIN?', default=False)
    exercicio_cadin = models.CharField('Exercício da cobrança de IPTU', max_length=15, blank=True)
    notificacao_cadin_municipal = models.CharField('Notificação CADIN Municipal', max_length=180, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']
        verbose_name = 'Imóvel'
        verbose_name_plural = 'Imóveis'

    def __str__(self):
        return f'{self.inscricao_imobiliaria} - {self.endereco_completo}'

    def clean(self):
        super().clean()
        # O tempo da imunidade só faz sentido quando o imóvel está marcado como imune.
        if self.imunidade and not self.tempo_imunidade:
            raise ValidationError({'tempo_imunidade': 'Informe o tempo de imunidade.'})
        if not self.imunidade:
            self.tempo_imunidade = None
        # Campos de CADIN só são obrigatórios e preservados quando há cobrança ativa.
        if self.possui_cadin and not self.exercicio_cadin:
            raise ValidationError({'exercicio_cadin': 'Informe o exercício do CADIN.'})
        if self.possui_cadin and not self.notificacao_cadin_municipal:
            raise ValidationError({'notificacao_cadin_municipal': 'Informe a notificação CADIN municipal.'})
        if not self.possui_cadin:
            self.exercicio_cadin = ''
            self.notificacao_cadin_municipal = ''

    @property
    def endereco_completo(self):
        """Monta endereço completo para listagens e cabeçalhos."""

        return f'{self.logradouro}, {self.numero} - {self.bairro} - {self.municipio}/{self.uf}'

    @property
    def possui_cadin_ativo(self):
        """Considera CADIN ativo até existir ciclo deferido que regularize o imóvel."""

        if not self.possui_cadin:
            return False
        return not self.ciclos.filter(resultado=CicloProcessual.Resultado.DEFERIDO).exists()

    def valor_monetario_display(self, value):
        """Formata decimais monetários no padrão brasileiro para exibição simples."""

        if value in (None, ''):
            return '-'
        decimal_value = Decimal(value).quantize(Decimal('0.01'))
        inteiro, fracionario = f'{decimal_value:.2f}'.split('.')
        inteiro_formatado = f'{int(inteiro):,}'.replace(',', '.')
        return f'{inteiro_formatado},{fracionario}'


class ImovelProcessoSEI(models.Model):
    """Processo SEI vinculado ao imóvel."""

    imovel = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='processos_sei')
    numero_sei = models.CharField('Número SEI', max_length=120)
    link_sei = models.URLField('Link SEI', max_length=500)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Processo SEI'
        verbose_name_plural = 'Processos SEI'

    def __str__(self):
        return self.numero_sei


class ImovelAnexo(models.Model):
    """Arquivo complementar associado ao imóvel."""

    imovel = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='anexos')
    nome_exibicao = models.CharField('Nome exibido', max_length=180)
    arquivo = models.FileField(upload_to='regulariza_sgi/anexos/')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Anexo do imóvel'
        verbose_name_plural = 'Anexos do imóvel'

    def __str__(self):
        return self.nome_exibicao


class ImovelObservacao(models.Model):
    """Observação de livre preenchimento registrada no histórico funcional do imóvel."""

    imovel = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='observacoes')
    texto = models.TextField('Observação')
    usuario_responsavel = models.CharField('Usuário responsável', max_length=150)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Observação do imóvel'
        verbose_name_plural = 'Observações do imóvel'

    def __str__(self):
        return f'Observação {self.pk} - {self.imovel_id}'


class CicloProcessual(models.Model):
    """Ciclo de protocolo, manifestação, deferimento/indeferimento e renovação."""

    class Tipo(models.TextChoices):
        INICIAL = 'inicial', 'Inicial'
        CONTRARRAZAO = 'contrarrazao', 'Contrarrazão'
        RENOVACAO = 'renovacao', 'Renovação'

    class Resultado(models.TextChoices):
        DEFERIDO = 'deferido', 'Deferido'
        INDEFERIDO = 'indeferido', 'Indeferido'

    imovel = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='ciclos')
    numero = models.PositiveIntegerField('Ciclo', default=1)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.INICIAL)
    data_inicio = models.DateField('Data inicial')
    numero_protocolo = models.CharField('Número do protocolo', max_length=120, blank=True)
    data_protocolo = models.DateField('Data do protocolo', null=True, blank=True)
    prazo_resposta_dias = models.PositiveIntegerField('Prazo de resposta', null=True, blank=True)
    prorrogacao_dias = models.PositiveIntegerField('Prorrogação (dias)', default=0)
    data_prorrogacao = models.DateField('Data da prorrogação', null=True, blank=True)
    data_manifestacao_prevista = models.DateField('Manifestação prevista', null=True, blank=True)
    data_manifestacao = models.DateField('Data da manifestação', null=True, blank=True)
    resultado = models.CharField('Resultado', max_length=20, choices=Resultado.choices, blank=True)
    prazo_imunidade_anos = models.PositiveIntegerField('Prazo da imunidade', null=True, blank=True)
    data_vencimento_imunidade = models.DateField('Vencimento da imunidade', null=True, blank=True)
    data_renovacao_prevista = models.DateField('Renovação prevista', null=True, blank=True)
    data_contrarrazao_limite = models.DateField('Prazo para contrarrazão', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-numero', '-id']
        unique_together = [('imovel', 'numero')]
        verbose_name = 'Ciclo processual'
        verbose_name_plural = 'Ciclos processuais'

    def __str__(self):
        return f'Ciclo {self.numero} - {self.get_tipo_display()}'


class MarcoProcessual(models.Model):
    """Marco calculado ou registrado dentro de um ciclo processual."""

    ciclo = models.ForeignKey(CicloProcessual, on_delete=models.CASCADE, related_name='marcos')
    tipo = models.CharField(max_length=40)
    titulo = models.CharField(max_length=120)
    ordem = models.PositiveIntegerField(default=1)
    data_real = models.DateField('Data real', null=True, blank=True)
    data_prevista = models.DateField('Data prevista', null=True, blank=True)
    prazo_dias = models.PositiveIntegerField('Prazo em dias', null=True, blank=True)
    usuario_responsavel = models.CharField('Usuário responsável', max_length=150, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Marco processual'
        verbose_name_plural = 'Marcos processuais'

    def __str__(self):
        return self.titulo


class ImovelTimelineEvento(models.Model):
    """Evento consolidado da linha do tempo do imóvel, incluindo ações cadastrais e processuais."""

    class Tipo(models.TextChoices):
        CADASTRO = 'cadastro', 'Cadastro'
        EDICAO = 'edicao', 'Edição'
        OBSERVACAO = 'observacao', 'Observação'
        ANEXO = 'anexo', 'Anexo'
        PROCESSO_SEI = 'processo_sei', 'Processo SEI'
        PROTOCOLO = 'protocolo', 'Protocolo'
        PRORROGACAO = 'prorrogacao', 'Prorrogação'
        MANIFESTACAO = 'manifestacao', 'Manifestação'
        CICLO = 'ciclo', 'Ciclo'

    imovel = models.ForeignKey(Imovel, on_delete=models.CASCADE, related_name='timeline_eventos')
    tipo = models.CharField('Tipo do evento', max_length=40, choices=Tipo.choices)
    descricao = models.TextField('Descrição')
    usuario_responsavel = models.CharField('Usuário responsável', max_length=150, blank=True)
    ciclo = models.ForeignKey('CicloProcessual', on_delete=models.SET_NULL, related_name='timeline_eventos', null=True, blank=True)
    anexo = models.ForeignKey('ImovelAnexo', on_delete=models.SET_NULL, related_name='timeline_eventos', null=True, blank=True)
    processo_sei = models.ForeignKey('ImovelProcessoSEI', on_delete=models.SET_NULL, related_name='timeline_eventos', null=True, blank=True)
    observacao = models.ForeignKey('ImovelObservacao', on_delete=models.SET_NULL, related_name='timeline_eventos', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Evento da timeline do imóvel'
        verbose_name_plural = 'Eventos da timeline do imóvel'

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.imovel_id}'
