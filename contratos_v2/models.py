# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Definir o domínio do Contratos V2 com checklist, competências, medição, avaliação e pagamento.

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max, Q, Sum
from django.utils import timezone

from contratos.models import EmpresaContratada
from contratos.services import quantize_money

from .services import (
    ZERO,
    criar_avaliacao_shell_competencia_v2,
    gerar_competencias_contrato_v2,
    recalcular_avaliacao_v2,
    recalcular_competencia_v2,
    sincronizar_checklist_ativo_contrato_v2,
    usuario_pode_gerir_contrato_v2,
    usuario_pode_preencher_avaliacao_v2,
    usuario_pode_preencher_checklist_v2,
    usuario_pode_preencher_medicao_v2,
)


class ContratoV2(models.Model):
    """Contrato simplificado da V2 com totais derivados dos itens e fluxo mensal de competências."""

    class Situacao(models.TextChoices):
        AUTOMATICA = '', 'Automática'
        VIGENTE = 'VIGENTE', 'Vigente'
        A_VENCER = 'A_VENCER', 'À vencer'
        ENCERRADO = 'ENCERRADO', 'Encerrado'
        SUSPENSO = 'SUSPENSO', 'Suspenso'

    numero_contrato = models.CharField('Número do contrato', max_length=80, unique=True)
    apelido = models.CharField('Apelido', max_length=180)
    objeto = models.CharField('Objeto do contrato', max_length=255)
    data_inicio_vigencia = models.DateField('Data de início da vigência')
    prazo_inicial_meses = models.PositiveIntegerField('Prazo inicial (meses)')
    vigencia_maxima_meses = models.PositiveIntegerField('Vigência máxima permitida (meses)')
    empresa_contratada = models.ForeignKey(
        EmpresaContratada,
        on_delete=models.PROTECT,
        related_name='contratos_v2',
        verbose_name='Empresa contratada',
    )
    fiscal_administrativo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contratos_v2_como_fiscal_administrativo',
        verbose_name='Fiscal administrativo',
    )
    fiscal_tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contratos_v2_como_fiscal_tecnico',
        verbose_name='Fiscal técnico',
    )
    gestor_contrato = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='contratos_v2_como_gestor',
        verbose_name='Gestor contrato',
    )
    base_mensal = models.DecimalField('Base mensal', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_global = models.DecimalField('Valor global do contrato', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    situacao_forcada = models.CharField(
        'Situação forçada',
        max_length=20,
        choices=Situacao.choices,
        blank=True,
        default='',
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contratos_v2_criados',
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='contratos_v2_atualizados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['numero_contrato', 'id']
        verbose_name = 'Contrato V2'
        verbose_name_plural = 'Contratos V2'

    def __str__(self):
        return f'{self.numero_contrato} - {self.apelido}'

    def save(self, *args, **kwargs):
        """Mantém os totais sincronizados quando a vigência muda depois do cadastro dos itens."""

        update_fields = kwargs.get('update_fields')
        atualizacao_financeira = bool(update_fields) and set(update_fields).issubset({'base_mensal', 'valor_global', 'atualizado_em'})
        super().save(*args, **kwargs)
        if not atualizacao_financeira and self.pk and self.itens.exists():
            self.refresh_financials()

    @property
    def vigencia_total_meses(self):
        """Enquanto a V2 não tem aditivos, a vigência total reflete o prazo inicial informado."""

        return int(self.prazo_inicial_meses or 0)

    @property
    def checklist_ativo(self):
        return self.checklist_modelos.filter(ativo=True).order_by('-atualizado_em', '-id').first()

    @property
    def formulario_avaliacao_ativo(self):
        return self.formularios_avaliacao.filter(ativo=True).order_by('-atualizado_em', '-id').first()

    def refresh_financials(self, save=True):
        """Consolida base mensal e valor global a partir dos itens vinculados ao contrato."""

        total_itens = self.itens.aggregate(total=Sum('valor_subtotal')).get('total') or Decimal('0.00')
        self.base_mensal = quantize_money(total_itens)
        self.valor_global = quantize_money(self.base_mensal * Decimal(self.vigencia_total_meses))
        if save:
            self.save(update_fields=['base_mensal', 'valor_global', 'atualizado_em'])

    def gerar_competencias(self):
        """Cria competências mensais da vigência inicial usando as configurações ativas do contrato."""

        gerar_competencias_contrato_v2(self)

    def usuario_pode_gerir(self, user):
        return usuario_pode_gerir_contrato_v2(user, self)

    def usuario_pode_preencher_checklist(self, user):
        return usuario_pode_preencher_checklist_v2(user, self)

    def usuario_pode_preencher_avaliacao(self, user):
        return usuario_pode_preencher_avaliacao_v2(user, self)

    def usuario_pode_preencher_medicao(self, user):
        return usuario_pode_preencher_medicao_v2(user, self)


class ContratoItemV2(models.Model):
    """Item financeiro do contrato usado para formar a base mensal e o valor global."""

    contrato = models.ForeignKey(ContratoV2, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveIntegerField('Item', default=1)
    descricao = models.TextField('Descrição')
    codigo_siafisico = models.CharField('Código SIAFÍSICO', max_length=120, blank=True)
    codigo_catmat_catser = models.CharField('Código CATMAT/CATSER', max_length=120, blank=True)
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_unitario = models.DecimalField('Valor unitário', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_subtotal = models.DecimalField('Valor subtotal', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        unique_together = [('contrato', 'ordem')]
        verbose_name = 'Item do contrato V2'
        verbose_name_plural = 'Itens do contrato V2'

    def __str__(self):
        return f'{self.ordem} - {self.descricao[:60]}'

    def save(self, *args, **kwargs):
        """Recalcula o subtotal no backend para evitar divergência entre tela e banco."""

        self.valor_subtotal = quantize_money((self.quantidade or Decimal('0.00')) * (self.valor_unitario or Decimal('0.00')))
        super().save(*args, **kwargs)
        self.contrato.refresh_financials()

    def delete(self, *args, **kwargs):
        contrato = self.contrato
        super().delete(*args, **kwargs)
        contrato.refresh_financials()


class ChecklistModeloV2(models.Model):
    """Versão do checklist documental do contrato usada para replicar competências."""

    contrato = models.ForeignKey(ContratoV2, on_delete=models.CASCADE, related_name='checklist_modelos')
    nome = models.CharField('Nome da versão', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    observacoes = models.TextField('Observações', blank=True)
    ativo = models.BooleanField('Ativo', default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-ativo', '-atualizado_em', '-id']
        verbose_name = 'Versão de checklist'
        verbose_name_plural = 'Versões de checklist'

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.ativo:
            type(self).objects.filter(contrato=self.contrato).exclude(pk=self.pk).update(ativo=False)
            sincronizar_checklist_ativo_contrato_v2(self.contrato)


class ChecklistModeloItemV2(models.Model):
    """Documento exigido dentro de uma versão de checklist do contrato."""

    modelo = models.ForeignKey(ChecklistModeloV2, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    titulo = models.CharField('Título', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    obrigatorio = models.BooleanField('Obrigatório', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        unique_together = [('modelo', 'ordem')]
        verbose_name = 'Item da versão de checklist'
        verbose_name_plural = 'Itens da versão de checklist'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if self.pk is None and not self.ordem:
            maior = type(self).objects.filter(modelo=self.modelo).aggregate(max_ordem=Max('ordem')).get('max_ordem') or 0
            self.ordem = maior + 1
        super().save(*args, **kwargs)
        if self.modelo.ativo:
            sincronizar_checklist_ativo_contrato_v2(self.modelo.contrato)

    def delete(self, *args, **kwargs):
        contrato = self.modelo.contrato
        modelo_ativo = self.modelo.ativo
        super().delete(*args, **kwargs)
        if modelo_ativo:
            sincronizar_checklist_ativo_contrato_v2(contrato)


class FormularioAvaliacaoV2(models.Model):
    """Versão do formulário de avaliação de qualidade do contrato."""

    contrato = models.ForeignKey(ContratoV2, on_delete=models.CASCADE, related_name='formularios_avaliacao')
    nome = models.CharField('Nome da avaliação', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    ativo = models.BooleanField('Ativo', default=False)
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-ativo', '-atualizado_em', '-id']
        verbose_name = 'Formulário de avaliação'
        verbose_name_plural = 'Formulários de avaliação'

    def __str__(self):
        return self.nome

    def clean(self):
        super().clean()
        if not self.contrato_id:
            return
        if self.pk is None and self.contrato.competencias.exists():
            raise ValidationError('Não é permitido cadastrar avaliação de qualidade após a geração de competências.')
        if self.pk and self.contrato.competencias.exists():
            raise ValidationError('Não é permitido alterar formulários de avaliação após a geração de competências.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        if self.ativo:
            type(self).objects.filter(contrato=self.contrato).exclude(pk=self.pk).update(ativo=False)

    def delete(self, *args, **kwargs):
        if self.contrato.competencias.exists():
            raise ValidationError('Não é permitido excluir formulários de avaliação após a geração de competências.')
        super().delete(*args, **kwargs)


class EscalaNotaAvaliacaoV2(models.Model):
    """Escala parametrizável de notas disponível para o formulário de avaliação."""

    formulario = models.ForeignKey(FormularioAvaliacaoV2, on_delete=models.CASCADE, related_name='escalas')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    valor = models.DecimalField('Valor numérico', max_digits=8, decimal_places=2)
    legenda = models.CharField('Legenda', max_length=120)

    class Meta:
        ordering = ['ordem', '-valor', 'id']
        unique_together = [('formulario', 'ordem')]
        verbose_name = 'Nota da escala'
        verbose_name_plural = 'Notas da escala'

    def __str__(self):
        return f'{self.valor} - {self.legenda}'


class FaixaLiberacaoAvaliacaoV2(models.Model):
    """Faixa de nota final usada para sugerir o percentual de liberação financeira."""

    formulario = models.ForeignKey(FormularioAvaliacaoV2, on_delete=models.CASCADE, related_name='faixas_liberacao')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    nota_minima = models.DecimalField('Nota mínima', max_digits=8, decimal_places=2)
    nota_maxima = models.DecimalField('Nota máxima', max_digits=8, decimal_places=2, null=True, blank=True)
    percentual_liberacao = models.DecimalField('Percentual de liberação', max_digits=8, decimal_places=2, default=Decimal('100.00'))

    class Meta:
        ordering = ['ordem', '-nota_minima', 'id']
        unique_together = [('formulario', 'ordem')]
        verbose_name = 'Faixa de liberação'
        verbose_name_plural = 'Faixas de liberação'

    def __str__(self):
        return f'{self.percentual_liberacao}% a partir de {self.nota_minima}'

    def clean(self):
        super().clean()
        if self.nota_maxima is not None and self.nota_maxima < self.nota_minima:
            raise ValidationError({'nota_maxima': 'A nota máxima deve ser maior ou igual à mínima.'})


class GrupoAvaliacaoV2(models.Model):
    """Grupo de itens de avaliação usado apenas para organizar visualmente o formulário."""

    formulario = models.ForeignKey(FormularioAvaliacaoV2, on_delete=models.CASCADE, related_name='grupos')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    nome = models.CharField('Nome', max_length=180)
    descricao = models.TextField('Descrição', blank=True)

    class Meta:
        ordering = ['ordem', 'id']
        unique_together = [('formulario', 'ordem')]
        verbose_name = 'Grupo de avaliação'
        verbose_name_plural = 'Grupos de avaliação'

    def __str__(self):
        return self.nome


class ItemAvaliacaoV2(models.Model):
    """Item avaliável dentro de um grupo da versão de avaliação."""

    grupo = models.ForeignKey(GrupoAvaliacaoV2, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveIntegerField('Ordem de exibição', default=1)
    descricao = models.TextField('Descrição do item')
    peso_percentual = models.DecimalField('Peso percentual dentro do grupo', max_digits=8, decimal_places=2, default=Decimal('100.00'))
    observacoes_padrao = models.TextField('Observação padrão', blank=True)

    class Meta:
        ordering = ['ordem', 'id']
        unique_together = [('grupo', 'ordem')]
        verbose_name = 'Item de avaliação'
        verbose_name_plural = 'Itens de avaliação'

    def __str__(self):
        return self.descricao[:80]


class CompetenciaPagamentoV2(models.Model):
    """Competência mensal única que concentra checklist, medição, avaliação e pagamento."""

    class Status(models.TextChoices):
        BLOQUEADA = 'BLOQUEADA', 'Bloqueada'
        CHECKLIST_PENDENTE = 'CHECKLIST_PENDENTE', 'Checklist pendente'
        MEDICAO_PENDENTE = 'MEDICAO_PENDENTE', 'Medição pendente'
        AVALIACAO_PENDENTE = 'AVALIACAO_PENDENTE', 'Avaliação pendente'
        PAGAMENTO_PENDENTE = 'PAGAMENTO_PENDENTE', 'Pagamento pendente'
        PAGA = 'PAGA', 'Paga'
        CANCELADA = 'CANCELADA', 'Cancelada'

    contrato = models.ForeignKey(ContratoV2, on_delete=models.CASCADE, related_name='competencias')
    periodo_inicio = models.DateField('Período inicial')
    periodo_fim = models.DateField('Período final')
    status = models.CharField('Status', max_length=30, choices=Status.choices, default=Status.BLOQUEADA)
    aplicar_pro_rata = models.BooleanField('Aplicar pró-rata', default=False)
    valor_previsto = models.DecimalField('Valor previsto', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_medido = models.DecimalField('Valor medido', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_liberado_sugerido = models.DecimalField('Valor liberado sugerido', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_liberado_final = models.DecimalField('Valor liberado final', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    checklist_modelo_snapshot = models.JSONField('Snapshot do checklist', default=dict, blank=True)
    formulario_avaliacao_snapshot = models.JSONField('Snapshot da avaliação', default=dict, blank=True)
    checklist_concluido_em = models.DateTimeField('Checklist concluído em', null=True, blank=True)
    medicao_concluida_em = models.DateTimeField('Medição concluída em', null=True, blank=True)
    data_pagamento = models.DateField('Data do pagamento', null=True, blank=True)
    nota_fiscal_fatura = models.FileField('Nota Fiscal/Fatura', upload_to='contratos_v2/pagamentos/', blank=True)
    atestado_realizacao = models.FileField('Atestado de Realização', upload_to='contratos_v2/pagamentos/', blank=True)
    despacho_dof = models.FileField('Despacho DOF', upload_to='contratos_v2/pagamentos/', blank=True)
    autorizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_autorizadas',
    )
    justificativa_divergencia = models.TextField('Justificativa de divergência', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['periodo_inicio', 'id']
        unique_together = [('contrato', 'periodo_inicio', 'periodo_fim')]
        verbose_name = 'Competência V2'
        verbose_name_plural = 'Competências V2'

    def __str__(self):
        return f'{self.contrato.numero_contrato} - {self.periodo_inicio:%m/%Y}'

    @property
    def exige_avaliacao(self):
        return bool(self.formulario_avaliacao_snapshot)

    @property
    def pode_pagar(self):
        return self.status == self.Status.PAGAMENTO_PENDENTE

    @property
    def avaliacao_qualidade_segura(self):
        try:
            return self.avaliacao_qualidade
        except AvaliacaoQualidadeCompetenciaV2.DoesNotExist:
            return None

    @property
    def checklist_estado(self):
        """Estado visual do botão de checklist no card da competência."""

        return 'done' if (not self.checklist_itens.filter(obrigatorio=True, concluido=False).exists() and self.checklist_itens.exists()) else 'idle'

    @property
    def medicao_estado(self):
        """Estado visual do botão de medição no card da competência."""

        return 'done' if self.medicao_concluida_em else 'idle'

    @property
    def avaliacao_estado(self):
        """Estado visual do botão de avaliação no card da competência."""

        avaliacao = self.avaliacao_qualidade_segura
        avaliacao_iniciada = bool(
            avaliacao
            and avaliacao.itens.filter(
                Q(nota_valor__isnull=False)
                | ~Q(justificativa_fiscal='')
                | ~Q(manifestacao_gestor_item='')
            ).exists()
        )

        if not self.exige_avaliacao:
            return 'idle'
        if getattr(avaliacao, 'concluida_em', None):
            return 'done'
        if avaliacao_iniciada:
            return 'pending'
        return 'idle'

    @property
    def pagamento_estado(self):
        """Estado visual do botão de pagamento no card da competência."""

        if self.status == self.Status.PAGA:
            return 'done'
        if self.status == self.Status.PAGAMENTO_PENDENTE:
            return 'pending'
        return 'idle'

    @property
    def etapas(self):
        """Mantém a estrutura textual para usos internos e testes existentes."""

        return [
            ('Checklist', self.checklist_estado),
            ('Medição', self.medicao_estado),
            ('Avaliação', self.avaliacao_estado),
            ('Pagamento', self.pagamento_estado),
        ]

    def save(self, *args, **kwargs):
        if not self.valor_previsto:
            self.valor_previsto = self.contrato.base_mensal
        super().save(*args, **kwargs)


class ChecklistCompetenciaItemV2(models.Model):
    """Snapshot documental que o fiscal precisa entregar dentro da competência."""

    competencia = models.ForeignKey(CompetenciaPagamentoV2, on_delete=models.CASCADE, related_name='checklist_itens')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    titulo = models.CharField('Título', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    obrigatorio = models.BooleanField('Obrigatório', default=True)
    concluido = models.BooleanField('Concluído', default=False)
    validado_em = models.DateTimeField('Validado em', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['ordem', 'id']
        verbose_name = 'Item do checklist da competência'
        verbose_name_plural = 'Itens do checklist da competência'

    def __str__(self):
        return self.titulo

    @property
    def anexo_principal(self):
        return getattr(self, 'anexo', None)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        recalcular_competencia_v2(self.competencia)


class ChecklistCompetenciaAnexoV2(models.Model):
    """Arquivo principal anexado ao item de checklist da competência."""

    item = models.OneToOneField(ChecklistCompetenciaItemV2, on_delete=models.CASCADE, related_name='anexo')
    arquivo = models.FileField('Arquivo', upload_to='contratos_v2/checklists/')
    nome_exibicao = models.CharField('Nome exibido', max_length=220, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Anexo do checklist da competência'
        verbose_name_plural = 'Anexos do checklist da competência'

    def __str__(self):
        return self.nome_exibicao or self.arquivo.name

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.item.concluido or not self.item.validado_em:
            self.item.concluido = True
            self.item.validado_em = timezone.now()
            self.item.save(update_fields=['concluido', 'validado_em'])

    def delete(self, *args, **kwargs):
        item = self.item
        super().delete(*args, **kwargs)
        item.concluido = False
        item.validado_em = None
        item.save(update_fields=['concluido', 'validado_em'])


class MedicaoItemCompetenciaV2(models.Model):
    """Quantidade medida por item do contrato dentro de uma competência mensal."""

    competencia = models.ForeignKey(CompetenciaPagamentoV2, on_delete=models.CASCADE, related_name='medicoes')
    item_contrato = models.ForeignKey(ContratoItemV2, on_delete=models.CASCADE, related_name='medicoes')
    quantidade = models.DecimalField('Quantidade', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_unitario_aplicado = models.DecimalField('Valor unitário aplicado', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_subtotal = models.DecimalField('Valor subtotal', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['item_contrato__ordem', 'id']
        unique_together = [('competencia', 'item_contrato')]
        verbose_name = 'Medição da competência'
        verbose_name_plural = 'Medições da competência'

    def __str__(self):
        return f'{self.competencia} - item {self.item_contrato.ordem}'

    def save(self, *args, **kwargs):
        self.valor_unitario_aplicado = self.valor_unitario_aplicado or self.item_contrato.valor_unitario
        self.valor_subtotal = quantize_money((self.quantidade or ZERO) * (self.valor_unitario_aplicado or ZERO))
        super().save(*args, **kwargs)
        recalcular_competencia_v2(self.competencia)

    def delete(self, *args, **kwargs):
        competencia = self.competencia
        super().delete(*args, **kwargs)
        recalcular_competencia_v2(competencia)


class AvaliacaoQualidadeCompetenciaV2(models.Model):
    """Avaliação efetiva aplicada a uma competência quando o contrato exige essa etapa."""

    competencia = models.OneToOneField(CompetenciaPagamentoV2, on_delete=models.CASCADE, related_name='avaliacao_qualidade')
    formulario = models.ForeignKey(FormularioAvaliacaoV2, on_delete=models.PROTECT, related_name='avaliacoes')
    formulario_snapshot = models.JSONField('Snapshot do formulário', default=dict, blank=True)
    nota_final = models.DecimalField('Nota final', max_digits=8, decimal_places=2, default=Decimal('0.00'))
    percentual_liberacao_sugerido = models.DecimalField('Percentual sugerido', max_digits=8, decimal_places=2, default=Decimal('100.00'))
    valor_liberado_sugerido = models.DecimalField('Valor sugerido', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    observacoes = models.TextField('Observações', blank=True)
    manifestacao_gestor = models.TextField('Manifestação do gestor', blank=True)
    preenchido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avaliacoes_v2_preenchidas',
    )
    concluida_em = models.DateTimeField('Concluída em', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['competencia__periodo_inicio', 'id']
        verbose_name = 'Avaliação da competência V2'
        verbose_name_plural = 'Avaliações das competências V2'

    def __str__(self):
        return f'{self.formulario.nome} - {self.competencia}'

    @property
    def maior_nota_escala(self):
        escala = self.formulario_snapshot.get('escala', [])
        if not escala:
            return ZERO
        return max(Decimal(item['valor']) for item in escala)

    @property
    def faixas_liberacao_snapshot(self):
        return self.formulario_snapshot.get('faixas_liberacao', [])


class AvaliacaoCompetenciaItemRespostaV2(models.Model):
    """Resposta lançada para cada item do snapshot da avaliação de qualidade."""

    avaliacao = models.ForeignKey(AvaliacaoQualidadeCompetenciaV2, on_delete=models.CASCADE, related_name='itens')
    grupo_nome = models.CharField('Grupo', max_length=180)
    grupo_ordem = models.PositiveIntegerField('Ordem do grupo', default=1)
    item_ordem = models.PositiveIntegerField('Ordem do item', default=1)
    item_descricao = models.TextField('Descrição do item')
    item_peso_percentual = models.DecimalField('Peso do item', max_digits=8, decimal_places=2, default=Decimal('100.00'))
    item_observacoes_padrao = models.TextField('Observações padrão', blank=True)
    nota_fiscal_valor = models.DecimalField('Nota do fiscal', max_digits=8, decimal_places=2, null=True, blank=True)
    nota_fiscal_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avaliacoes_v2_notas_fiscais',
    )
    nota_fiscal_preenchida_em = models.DateTimeField('Nota do fiscal preenchida em', null=True, blank=True)
    nota_gestor_valor = models.DecimalField('Nota do gestor', max_digits=8, decimal_places=2, null=True, blank=True)
    nota_gestor_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avaliacoes_v2_notas_gestor',
    )
    nota_gestor_preenchida_em = models.DateTimeField('Nota do gestor preenchida em', null=True, blank=True)
    nota_valor = models.DecimalField('Nota atribuída', max_digits=8, decimal_places=2, null=True, blank=True)
    nota_legenda = models.CharField('Legenda da nota', max_length=120, blank=True)
    justificativa_fiscal = models.TextField('Justificativa do fiscal', blank=True)
    justificativa_fiscal_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avaliacoes_v2_justificativas_fiscais',
    )
    justificativa_fiscal_preenchida_em = models.DateTimeField('Justificativa do fiscal preenchida em', null=True, blank=True)
    manifestacao_gestor_item = models.TextField('Manifestação do gestor no item', blank=True)
    manifestacao_gestor_item_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='avaliacoes_v2_manifestacoes_gestor',
    )
    manifestacao_gestor_item_preenchida_em = models.DateTimeField('Manifestação do gestor preenchida em', null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['grupo_ordem', 'item_ordem', 'id']
        verbose_name = 'Resposta de item da avaliação'
        verbose_name_plural = 'Respostas de itens da avaliação'

    def __str__(self):
        return self.item_descricao[:80]

    @property
    def nota_vigente(self):
        """Nota que prevalece no cálculo: a do gestor, quando existir, ou a do fiscal."""

        if self.nota_gestor_valor is not None:
            return self.nota_gestor_valor
        if self.nota_fiscal_valor is not None:
            return self.nota_fiscal_valor
        return self.nota_valor

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        recalcular_avaliacao_v2(self.avaliacao)
