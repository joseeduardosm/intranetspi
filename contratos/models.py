# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Definir o domínio de contratos, vigência, execução financeira e qualidade.

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max, Sum
from django.utils import timezone

from .services import (
    ZERO,
    calcular_memorias_retroativas,
    calcular_valor_previsto_competencia,
    contrato_alerta,
    contrato_data_final_vigente,
    contrato_data_limite_ordinaria,
    contrato_periodo_acumulado_texto,
    contrato_prazo_atual_texto,
    contrato_prazo_total_meses,
    contrato_regime,
    contrato_situacao,
    contrato_total_itens,
    contrato_valor_global,
    criar_checklist_competencia,
    quantize_money,
    recalcular_avaliacao,
    recalcular_competencia,
    reordenar_checklist_padrao_contrato,
    snapshot_modelo_qualidade,
    sincronizar_checklist_contrato,
    sync_competencias_pagamento,
)


def hora_local_atual():
    """Retorna apenas o componente de hora local para defaults do diário de bordo."""

    return timezone.localtime().time().replace(microsecond=0)


class EmpresaContratada(models.Model):
    """Cadastro centralizado das empresas contratadas."""

    razao_social = models.CharField('Razão social', max_length=220)
    cnpj = models.CharField('CNPJ', max_length=20, unique=True)
    nome_fantasia = models.CharField('Nome fantasia', max_length=220, blank=True)
    logradouro = models.CharField('Logradouro', max_length=255, blank=True)
    numero = models.CharField('Número', max_length=40, blank=True)
    complemento = models.CharField('Complemento', max_length=120, blank=True)
    bairro = models.CharField('Bairro', max_length=120, blank=True)
    cidade = models.CharField('Cidade', max_length=120, blank=True)
    estado = models.CharField('Estado', max_length=2, blank=True)
    cep = models.CharField('CEP', max_length=20, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['razao_social', 'cnpj']
        verbose_name = 'Empresa contratada'
        verbose_name_plural = 'Empresas contratadas'

    def __str__(self):
        return self.razao_social


class ResponsavelEmpresa(models.Model):
    """Responsáveis contratuais vinculados à empresa."""

    empresa = models.ForeignKey(EmpresaContratada, on_delete=models.CASCADE, related_name='responsaveis')
    nome = models.CharField('Nome', max_length=220)
    cpf = models.CharField('CPF', max_length=20, blank=True)
    cargo = models.CharField('Cargo', max_length=180, blank=True)
    telefone = models.CharField('Telefone', max_length=60, blank=True)
    email = models.EmailField('E-mail', blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nome', 'id']
        verbose_name = 'Responsável da empresa'
        verbose_name_plural = 'Responsáveis da empresa'

    def __str__(self):
        return f'{self.nome} - {self.empresa.razao_social}'


class Contrato(models.Model):
    """Entidade principal que preserva todo o histórico do contrato administrativo."""

    class Situacao(models.TextChoices):
        VIGENTE = 'VIGENTE', 'Vigente'
        A_VENCER = 'A_VENCER', 'A vencer'
        ENCERRADO = 'ENCERRADO', 'Encerrado'
        SUSPENSO = 'SUSPENSO', 'Suspenso'

    class Regime(models.TextChoices):
        ORDINARIO = 'ORDINARIO', 'Ordinário'
        EXCEPCIONAL = 'EXCEPCIONAL', 'Excepcional'
        EMERGENCIAL = 'EMERGENCIAL', 'Emergencial'

    numero_contrato = models.CharField('Número do contrato', max_length=80, unique=True)
    apelido = models.CharField('Apelido', max_length=180)
    objeto = models.CharField('Objeto do contrato', max_length=255)
    detalhamento_objeto = models.TextField('Detalhamento do objeto', blank=True)
    data_inicio_vigencia = models.DateField('Data de início da vigência')
    prazo_inicial_meses = models.PositiveIntegerField('Prazo inicial (meses)')
    vigencia_maxima_meses = models.PositiveIntegerField('Vigência máxima permitida (meses)')
    empresa_contratada = models.ForeignKey(EmpresaContratada, on_delete=models.PROTECT, related_name='contratos')
    fiscal_administrativo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contratos_como_fiscal_administrativo',
    )
    fiscal_tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contratos_como_fiscal_tecnico',
    )
    gestor_contrato = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contratos_como_gestor',
    )
    base_mensal = models.DecimalField('Base mensal', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_global = models.DecimalField('Valor global do contrato', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    situacao_forcada = models.CharField(
        'Situação forçada',
        max_length=20,
        choices=[('', 'Automática')] + list(Situacao.choices),
        blank=True,
        default='',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contratos_criados',
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contratos_atualizados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['numero_contrato', 'id']
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'

    def __str__(self):
        return f'{self.numero_contrato} - {self.apelido}'

    def save(self, *args, **kwargs):
        """Persiste o contrato e mantém a agenda automática de competências alinhada à vigência."""

        super().save(*args, **kwargs)
        sync_competencias_pagamento(self)

    def refresh_financials(self, save=True):
        """Atualiza base mensal e valor global consolidado a partir dos itens e da vigência."""

        self.base_mensal = contrato_total_itens(self)
        self.valor_global = contrato_valor_global(self)
        if save:
            self.save(update_fields=['base_mensal', 'valor_global', 'atualizado_em'])
        else:
            sync_competencias_pagamento(self)

    @property
    def data_limite_vigencia(self):
        return contrato_data_limite_ordinaria(self)

    @property
    def data_final_vigencia(self):
        return contrato_data_final_vigente(self)

    @property
    def situacao_atual(self):
        return contrato_situacao(self)

    @property
    def regime_atual(self):
        return contrato_regime(self)

    @property
    def situacao_atual_display(self):
        return self.Situacao(self.situacao_atual).label

    @property
    def regime_atual_display(self):
        return self.Regime(self.regime_atual).label

    @property
    def prazo_atual_display(self):
        return contrato_prazo_atual_texto(self)

    @property
    def periodo_acumulado_display(self):
        return contrato_periodo_acumulado_texto(self)

    @property
    def vigencia_total_meses(self):
        return contrato_prazo_total_meses(self)

    @property
    def alerta_vigencia(self):
        return contrato_alerta(self)

    @property
    def possui_checklist_padrao(self):
        """Indica se o contrato já tem checklist padrão suficiente para liberar as competências."""

        return self.checklist_modelos.exists()

    def sync_detalhamento_texto(self, save=True):
        """Consolida os itens estruturados em texto para manter compatibilidade com o campo legado."""

        linhas = [f'{item.ordem}. {item.descricao}' for item in self.detalhamento_itens.order_by('ordem', 'id') if item.descricao.strip()]
        self.detalhamento_objeto = '\n'.join(linhas)
        if save:
            self.save(update_fields=['detalhamento_objeto', 'atualizado_em'])


class ContratoDetalhamentoItem(models.Model):
    """Item estruturado do detalhamento do objeto contratual."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='detalhamento_itens')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    descricao = models.TextField('Descrição')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Item do detalhamento do objeto'
        verbose_name_plural = 'Itens do detalhamento do objeto'

    def __str__(self):
        return f'{self.ordem}. {self.descricao[:60]}'


class ContratoItem(models.Model):
    """Item do objeto contratado com base para medições e reajustes."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveIntegerField('Item', default=1)
    descricao = models.TextField('Descrição')
    codigo_siafisico = models.CharField('Código SIAFÍSICO', max_length=120, blank=True)
    codigo_catmat_catser = models.CharField('Código CATMAT/CATSER', max_length=120, blank=True)
    unidade_fornecimento = models.CharField('Unidade de fornecimento', max_length=120, blank=True)
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_unitario = models.DecimalField('Valor unitário', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_subtotal = models.DecimalField('Valor subtotal', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_referencial = models.DecimalField(
        'Valor referencial',
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00'),
        blank=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        unique_together = [('contrato', 'ordem')]
        verbose_name = 'Item do contrato'
        verbose_name_plural = 'Itens do contrato'

    def __str__(self):
        return f'{self.ordem} - {self.descricao[:60]}'

    def save(self, *args, **kwargs):
        # O subtotal é sempre recalculado no backend para manter consistência financeira.
        self.valor_subtotal = quantize_money(self.quantidade * self.valor_unitario)
        super().save(*args, **kwargs)
        self.contrato.refresh_financials()

    def delete(self, *args, **kwargs):
        contrato = self.contrato
        super().delete(*args, **kwargs)
        contrato.refresh_financials()


class TermoAditivo(models.Model):
    """Histórico de aditivos e prorrogações vinculados ao contrato original."""

    class Tipo(models.TextChoices):
        PRORROGACAO = 'PRORROGACAO', 'Prorrogação'
        REAJUSTE = 'REAJUSTE', 'Reajuste'
        REPACTUACAO = 'REPACTUACAO', 'Repactuação'
        OUTRO = 'OUTRO', 'Outro'

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='aditivos')
    numero_termo = models.CharField('Número do termo aditivo', max_length=80)
    tipo = models.CharField('Tipo', max_length=20, choices=Tipo.choices, default=Tipo.PRORROGACAO)
    data_assinatura = models.DateField('Data de assinatura')
    data_inicio = models.DateField('Data de início')
    data_termino = models.DateField('Data de término')
    quantidade_meses = models.PositiveIntegerField('Quantidade de meses', default=0)
    justificativa = models.TextField('Justificativa', blank=True)
    documento_anexo = models.FileField('Documento anexo', upload_to='contratos/aditivos/', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['data_inicio', 'id']
        verbose_name = 'Termo aditivo'
        verbose_name_plural = 'Termos aditivos'

    def __str__(self):
        return f'{self.numero_termo} - {self.contrato.numero_contrato}'

    def clean(self):
        super().clean()
        if self.data_termino < self.data_inicio:
            raise ValidationError({'data_termino': 'A data de término deve ser posterior à data de início.'})

    def save(self, *args, **kwargs):
        """Recalcula a grade de competências quando a vigência é prorrogada por aditivo."""

        super().save(*args, **kwargs)
        sync_competencias_pagamento(self.contrato)


class DocumentoContrato(models.Model):
    """Repositório documental geral do contrato."""

    class Tipo(models.TextChoices):
        CONTRATO = 'CONTRATO', 'Contrato'
        TERMO_ADITIVO = 'TERMO_ADITIVO', 'Termo aditivo'
        APOSTILAMENTO = 'APOSTILAMENTO', 'Apostilamento'
        PARECER = 'PARECER', 'Parecer'
        NOTA_FISCAL = 'NOTA_FISCAL', 'Nota fiscal'
        ORDEM_SERVICO = 'ORDEM_SERVICO', 'Ordem de serviço'
        OUTRO = 'OUTRO', 'Outro'

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='documentos')
    tipo = models.CharField('Tipo documental', max_length=30, choices=Tipo.choices)
    descricao = models.CharField('Descrição', max_length=220)
    arquivo = models.FileField('Arquivo', upload_to='contratos/documentos/')
    data_documento = models.DateField('Data do documento', default=timezone.localdate)
    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_contrato_registrados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_documento', '-id']
        verbose_name = 'Documento do contrato'
        verbose_name_plural = 'Documentos do contrato'

    def __str__(self):
        return self.descricao


class OcorrenciaContrato(models.Model):
    """Entrada do diário de bordo contratual."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='ocorrencias')
    data_registro = models.DateField('Data', default=timezone.localdate)
    hora_registro = models.TimeField('Hora', default=hora_local_atual)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ocorrencias_contrato',
    )
    tipo_ocorrencia = models.CharField('Tipo da ocorrência', max_length=120)
    descricao = models.TextField('Descrição')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data_registro', '-hora_registro', '-id']
        verbose_name = 'Ocorrência contratual'
        verbose_name_plural = 'Ocorrências contratuais'

    def __str__(self):
        return f'{self.tipo_ocorrencia} - {self.contrato.numero_contrato}'


class OcorrenciaContratoAnexo(models.Model):
    """Anexo individual do diário de bordo."""

    ocorrencia = models.ForeignKey(OcorrenciaContrato, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField('Arquivo', upload_to='contratos/ocorrencias/')
    nome_exibicao = models.CharField('Nome exibido', max_length=220, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Anexo da ocorrência'
        verbose_name_plural = 'Anexos da ocorrência'

    def __str__(self):
        return self.nome_exibicao or self.arquivo.name


class CompetenciaPagamento(models.Model):
    """Competência financeira com checklist, medições e liberação de pagamento."""

    class Status(models.TextChoices):
        BLOQUEADO = 'BLOQUEADO', 'Bloqueado'
        RASCUNHO = 'RASCUNHO', 'Rascunho'
        EM_CONFERENCIA = 'EM_CONFERENCIA', 'Em conferência'
        APTO_LIBERACAO = 'APTO_LIBERACAO', 'Apto para liberação'
        PAGO = 'PAGO', 'Pago'
        CANCELADO = 'CANCELADO', 'Cancelado'

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='competencias')
    periodo_inicio = models.DateField('Período inicial')
    periodo_fim = models.DateField('Período final')
    nota_fiscal = models.CharField('Nota fiscal', max_length=120, blank=True)
    anexo_nota_fiscal = models.FileField('Anexo da nota fiscal', upload_to='contratos/pagamentos/', blank=True)
    anexo_atestado_realizacao = models.FileField('Atestado de realização', upload_to='contratos/pagamentos/', blank=True)
    anexo_despacho_dof = models.FileField('Despacho DOF', upload_to='contratos/pagamentos/', blank=True)
    status = models.CharField('Status', max_length=20, choices=Status.choices, default=Status.RASCUNHO)
    valor_previsto = models.DecimalField('Valor previsto', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_medido = models.DecimalField('Valor medido', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_liberado = models.DecimalField('Valor liberado', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    gerada_automaticamente = models.BooleanField('Gerada automaticamente', default=True)
    data_efetivacao = models.DateField('Data de efetivação', null=True, blank=True)
    usuario_responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_pagamento_responsavel',
    )
    confirmada_documentacao_em = models.DateTimeField('Confirmação documental', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-periodo_inicio', '-id']
        unique_together = [('contrato', 'periodo_inicio', 'periodo_fim')]
        verbose_name = 'Competência de pagamento'
        verbose_name_plural = 'Competências de pagamento'

    def __str__(self):
        return f'{self.contrato.numero_contrato} - {self.periodo_inicio:%m/%Y}'

    def clean(self):
        super().clean()
        if self.periodo_fim < self.periodo_inicio:
            raise ValidationError({'periodo_fim': 'O período final deve ser posterior ao período inicial.'})

    def save(self, *args, **kwargs):
        # Mantém o valor previsto sincronizado com a base mensal sempre que o período mudar.
        self.valor_previsto = calcular_valor_previsto_competencia(self.contrato, self.periodo_inicio, self.periodo_fim)
        if self.aguardando_checklist_padrao:
            self.status = self.Status.BLOQUEADO
        nova = self.pk is None
        super().save(*args, **kwargs)
        if nova:
            criar_checklist_competencia(self)
        recalcular_competencia(self)

    @property
    def pode_liberar(self):
        return not self.aguardando_checklist_padrao and not self.checklist_itens.filter(obrigatorio=True, concluido=False).exists()

    @property
    def aguardando_checklist_padrao(self):
        """Bloqueia a competência até existir checklist padrão do contrato replicado nela."""

        if not self.contrato.possui_checklist_padrao:
            return True
        if not self.pk:
            return False
        return not self.checklist_itens.exists()


class ChecklistPagamentoModelo(models.Model):
    """Definição do checklist obrigatório por contrato."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='checklist_modelos')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    titulo = models.CharField('Título', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    obrigatorio = models.BooleanField('Obrigatório', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Modelo de checklist'
        verbose_name_plural = 'Modelos de checklist'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        """Numera automaticamente o checklist padrão em sequência dentro do contrato."""

        if self.pk is None:
            maior_ordem = (
                type(self).objects.filter(contrato=self.contrato).aggregate(max_ordem=Max('ordem')).get('max_ordem') or 0
            )
            self.ordem = maior_ordem + 1
        super().save(*args, **kwargs)
        reordenar_checklist_padrao_contrato(self.contrato)
        sincronizar_checklist_contrato(self.contrato)


class ChecklistPagamentoItem(models.Model):
    """Snapshot do checklist em uma competência específica."""

    competencia = models.ForeignKey(CompetenciaPagamento, on_delete=models.CASCADE, related_name='checklist_itens')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    titulo = models.CharField('Título', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    obrigatorio = models.BooleanField('Obrigatório', default=True)
    concluido = models.BooleanField('Concluído', default=False)
    validado_em = models.DateTimeField('Validado em', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Item do checklist'
        verbose_name_plural = 'Itens do checklist'

    def __str__(self):
        return self.titulo

    @property
    def anexo_principal(self):
        """Retorna o anexo corrente do item para edição, visualização e limpeza na tela."""

        return self.anexos.order_by('-id').first()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        recalcular_competencia(self.competencia)


class ChecklistPagamentoAnexo(models.Model):
    """Arquivos apresentados para um item obrigatório do checklist."""

    item = models.ForeignKey(ChecklistPagamentoItem, on_delete=models.CASCADE, related_name='anexos')
    arquivo = models.FileField('Arquivo', upload_to='contratos/checklist/')
    nome_exibicao = models.CharField('Nome exibido', max_length=220, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Anexo do checklist'
        verbose_name_plural = 'Anexos do checklist'

    def __str__(self):
        return self.nome_exibicao or self.arquivo.name

    def save(self, *args, **kwargs):
        """Ao anexar um documento, conclui automaticamente o item do checklist correspondente."""

        super().save(*args, **kwargs)
        if not self.item.concluido or not self.item.validado_em:
            self.item.concluido = True
            self.item.validado_em = timezone.now()
            self.item.save(update_fields=['concluido', 'validado_em'])

    def delete(self, *args, **kwargs):
        """Ao limpar o último anexo, devolve o item ao estado pendente para novo upload."""

        item = self.item
        super().delete(*args, **kwargs)
        if not item.anexos.exists():
            item.concluido = False
            item.validado_em = None
            item.save(update_fields=['concluido', 'validado_em'])


class MedicaoItemCompetencia(models.Model):
    """Medição financeira por item do contrato em cada competência."""

    competencia = models.ForeignKey(CompetenciaPagamento, on_delete=models.CASCADE, related_name='medicoes')
    item_contrato = models.ForeignKey(ContratoItem, on_delete=models.CASCADE, related_name='medicoes')
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_unitario_aplicado = models.DecimalField('Valor unitário aplicado', max_digits=14, decimal_places=2)
    valor_subtotal = models.DecimalField('Valor subtotal', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_contrato__ordem', 'id']
        verbose_name = 'Medição de item'
        verbose_name_plural = 'Medições de itens'

    def __str__(self):
        return f'{self.competencia} - item {self.item_contrato.ordem}'

    def save(self, *args, **kwargs):
        self.valor_subtotal = quantize_money(self.quantidade * self.valor_unitario_aplicado)
        super().save(*args, **kwargs)
        recalcular_competencia(self.competencia)
        recalcular_avaliacao(self.competencia)

    def delete(self, *args, **kwargs):
        competencia = self.competencia
        super().delete(*args, **kwargs)
        recalcular_competencia(competencia)
        recalcular_avaliacao(competencia)


class ModeloAvaliacaoQualidade(models.Model):
    """Modelo de avaliação de qualidade configurado pelo gestor do contrato."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='modelos_qualidade')
    nome = models.CharField('Nome', max_length=180)
    vigencia_inicio = models.DateField('Vigência início')
    vigencia_fim = models.DateField('Vigência fim', null=True, blank=True)
    ativo = models.BooleanField('Ativo', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-vigencia_inicio', '-id']
        verbose_name = 'Modelo de avaliação'
        verbose_name_plural = 'Modelos de avaliação'

    def __str__(self):
        return self.nome


class GrupoAvaliacaoQualidade(models.Model):
    """Grupo de critérios para estruturar a avaliação."""

    modelo = models.ForeignKey(ModeloAvaliacaoQualidade, on_delete=models.CASCADE, related_name='grupos')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    nome = models.CharField('Nome', max_length=180)
    peso = models.DecimalField('Peso do grupo', max_digits=8, decimal_places=2, default=Decimal('1.00'))

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Grupo de avaliação'
        verbose_name_plural = 'Grupos de avaliação'

    def __str__(self):
        return self.nome


class CriterioAvaliacaoQualidade(models.Model):
    """Critério pontuável de qualidade contratual."""

    grupo = models.ForeignKey(GrupoAvaliacaoQualidade, on_delete=models.CASCADE, related_name='criterios')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    nome = models.CharField('Nome', max_length=220)
    descricao = models.TextField('Descrição', blank=True)
    peso = models.DecimalField('Peso', max_digits=8, decimal_places=2, default=Decimal('1.00'))
    pontuacao_maxima = models.DecimalField('Pontuação máxima', max_digits=8, decimal_places=2, default=Decimal('10.00'))

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Critério de avaliação'
        verbose_name_plural = 'Critérios de avaliação'

    def __str__(self):
        return self.nome


class AvaliacaoQualidadeCompetencia(models.Model):
    """Avaliação efetivamente aplicada à competência financeira."""

    competencia = models.OneToOneField(CompetenciaPagamento, on_delete=models.CASCADE, related_name='avaliacao_qualidade')
    modelo = models.ForeignKey(ModeloAvaliacaoQualidade, on_delete=models.PROTECT, related_name='avaliacoes')
    snapshot_modelo = models.JSONField('Snapshot do modelo', default=dict, blank=True)
    percentual_desempenho = models.DecimalField('Percentual de desempenho', max_digits=8, decimal_places=2, default=Decimal('0.00'))
    percentual_desconto = models.DecimalField('Percentual de desconto', max_digits=8, decimal_places=2, default=Decimal('0.00'))
    valor_ajuste = models.DecimalField('Valor do ajuste', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_final_ajustado = models.DecimalField('Valor final ajustado', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-competencia__periodo_inicio']
        verbose_name = 'Avaliação da competência'
        verbose_name_plural = 'Avaliações da competência'

    def __str__(self):
        return f'Avaliação {self.competencia}'

    def save(self, *args, **kwargs):
        if not self.snapshot_modelo:
            self.snapshot_modelo = snapshot_modelo_qualidade(self.modelo)
        super().save(*args, **kwargs)
        recalcular_avaliacao(self.competencia)
        recalcular_competencia(self.competencia)


class AvaliacaoCriterioCompetencia(models.Model):
    """Pontuação registrada para cada critério da competência."""

    avaliacao = models.ForeignKey(AvaliacaoQualidadeCompetencia, on_delete=models.CASCADE, related_name='itens')
    criterio = models.ForeignKey(CriterioAvaliacaoQualidade, on_delete=models.PROTECT, related_name='avaliacoes')
    nota_obtida = models.DecimalField('Nota obtida', max_digits=8, decimal_places=2, default=Decimal('0.00'))
    observacoes = models.TextField('Observações', blank=True)

    class Meta:
        ordering = ['criterio__grupo__ordem', 'criterio__ordem', 'id']
        verbose_name = 'Pontuação de critério'
        verbose_name_plural = 'Pontuações de critérios'

    def __str__(self):
        return f'{self.criterio.nome} - {self.avaliacao.competencia}'

    def clean(self):
        super().clean()
        if self.nota_obtida > self.criterio.pontuacao_maxima:
            raise ValidationError({'nota_obtida': 'A nota não pode ultrapassar a pontuação máxima do critério.'})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        recalcular_avaliacao(self.avaliacao.competencia)
        recalcular_competencia(self.avaliacao.competencia)


class EventoFinanceiroContrato(models.Model):
    """Evento de reajuste ou repactuação com memória retroativa."""

    class Tipo(models.TextChoices):
        REAJUSTE = 'REAJUSTE', 'Reajuste'
        REPACTUACAO = 'REPACTUACAO', 'Repactuação'

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='eventos_financeiros')
    tipo = models.CharField('Tipo', max_length=20, choices=Tipo.choices)
    indice_aplicado = models.CharField('Índice aplicado', max_length=120)
    data_base = models.DateField('Data-base')
    data_aplicacao = models.DateField('Data de aplicação')
    percentual_aplicado = models.DecimalField('Percentual aplicado', max_digits=8, decimal_places=2)
    justificativa = models.TextField('Justificativa', blank=True)
    historico = models.TextField('Histórico', blank=True)
    documento_anexo = models.FileField('Documento anexo', upload_to='contratos/eventos/', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_base', '-id']
        verbose_name = 'Evento financeiro'
        verbose_name_plural = 'Eventos financeiros'

    def __str__(self):
        return f'{self.get_tipo_display()} - {self.contrato.numero_contrato}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        calcular_memorias_retroativas(self)


class EventoFinanceiroItem(models.Model):
    """Item afetado pelo evento de reajuste ou repactuação."""

    evento = models.ForeignKey(EventoFinanceiroContrato, on_delete=models.CASCADE, related_name='itens')
    item_contrato = models.ForeignKey(ContratoItem, on_delete=models.CASCADE, related_name='eventos_financeiros')
    valor_original = models.DecimalField('Valor original', max_digits=14, decimal_places=2)
    valor_reajustado = models.DecimalField('Valor reajustado', max_digits=14, decimal_places=2)
    valor_referencial = models.DecimalField('Valor referencial', max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['item_contrato__ordem', 'id']
        verbose_name = 'Item do evento financeiro'
        verbose_name_plural = 'Itens do evento financeiro'

    def __str__(self):
        return f'Evento {self.evento_id} - item {self.item_contrato.ordem}'

    def clean(self):
        super().clean()
        if self.valor_referencial and self.valor_reajustado > self.valor_referencial:
            raise ValidationError({'valor_reajustado': 'O valor reajustado não pode ultrapassar o valor referencial.'})

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        calcular_memorias_retroativas(self.evento)


class MemoriaRetroatividade(models.Model):
    """Memória de cálculo da diferença retroativa por competência e item."""

    evento = models.ForeignKey(EventoFinanceiroContrato, on_delete=models.CASCADE, related_name='memorias')
    competencia = models.ForeignKey(CompetenciaPagamento, on_delete=models.CASCADE, related_name='memorias_retroativas')
    item_contrato = models.ForeignKey(ContratoItem, on_delete=models.CASCADE, related_name='memorias_retroativas')
    quantidade_base = models.DecimalField('Quantidade base', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_unitario_anterior = models.DecimalField('Valor unitário anterior', max_digits=14, decimal_places=2)
    valor_unitario_reajustado = models.DecimalField('Valor unitário reajustado', max_digits=14, decimal_places=2)
    diferenca_total = models.DecimalField('Diferença total', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['competencia__periodo_inicio', 'item_contrato__ordem', 'id']
        unique_together = [('evento', 'competencia', 'item_contrato')]
        verbose_name = 'Memória de retroatividade'
        verbose_name_plural = 'Memórias de retroatividade'

    def __str__(self):
        return f'{self.evento} - {self.competencia}'
