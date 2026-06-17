# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Definir o domínio do Contratos V2 com checklist, competências, medição, avaliação e pagamento.

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Max, Q, Sum
from django.utils import timezone

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
    """Contrato simplificado da V2 com totais derivados dos itens e fluxo mensal de competências."""

    class Situacao(models.TextChoices):
        AUTOMATICA = '', 'Automática'
        VIGENTE = 'VIGENTE', 'Vigente'
        A_VENCER = 'A_VENCER', 'À vencer'
        ENCERRADO = 'ENCERRADO', 'Encerrado'
        SUSPENSO = 'SUSPENSO', 'Suspenso'

    class MesReajuste(models.TextChoices):
        JANEIRO = '01', 'Janeiro'
        FEVEREIRO = '02', 'Fevereiro'
        MARCO = '03', 'Março'
        ABRIL = '04', 'Abril'
        MAIO = '05', 'Maio'
        JUNHO = '06', 'Junho'
        JULHO = '07', 'Julho'
        AGOSTO = '08', 'Agosto'
        SETEMBRO = '09', 'Setembro'
        OUTUBRO = '10', 'Outubro'
        NOVEMBRO = '11', 'Novembro'
        DEZEMBRO = '12', 'Dezembro'

    numero_contrato = models.CharField('Número do contrato', max_length=80, unique=True)
    apelido = models.CharField('Apelido', max_length=180)
    objeto = models.CharField('Objeto do contrato', max_length=255)
    data_inicio_vigencia = models.DateField('Data de início da vigência')
    prazo_inicial_meses = models.PositiveIntegerField('Prazo inicial (meses)')
    vigencia_maxima_meses = models.PositiveIntegerField('Vigência máxima permitida (meses)')
    mes_reajuste = models.CharField('Mês de reajuste', max_length=2, choices=MesReajuste.choices, blank=True, default='')
    empresa_contratada = models.ForeignKey(
        EmpresaContratada,
        on_delete=models.PROTECT,
        related_name='contratos',
        verbose_name='Empresa contratada',
    )
    # Os dois processos SEI ficam separados em número e link para refletir exatamente o fluxo exigido pelo usuário.
    processo_sei_gestao_numero = models.CharField('Processo SEI (Gestão) - número', max_length=120, blank=True, default='')
    processo_sei_gestao_url = models.URLField('Processo SEI (Gestão) - link', blank=True, default='')
    processo_sei_execucao_numero = models.CharField('Processo SEI (Execução) - número', max_length=120, blank=True, default='')
    processo_sei_execucao_url = models.URLField('Processo SEI (Execução) - link', blank=True, default='')
    fiscal_administrativo = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contratos_como_fiscal_administrativo',
        verbose_name='Fiscal administrativo',
    )
    fiscal_tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contratos_como_fiscal_tecnico',
        verbose_name='Fiscal técnico',
    )
    gestor_contrato = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contratos_como_gestor',
        verbose_name='Gestor contrato',
    )
    gestor_contrato_suplente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contratos_como_gestor_suplente',
        verbose_name='Gestor suplente',
    )
    fiscal_administrativo_suplente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contratos_como_fiscal_administrativo_suplente',
        verbose_name='Fiscal administrativo suplente',
    )
    fiscal_tecnico_suplente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='contratos_como_fiscal_tecnico_suplente',
        verbose_name='Fiscal técnico suplente',
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

    @property
    def valor_executado(self):
        """Soma do valor medido em todas as competências do contrato."""
        total = self.competencias.aggregate(total=Sum('valor_medido')).get('total') or Decimal('0.00')
        return total

    @property
    def valor_saldo(self):
        """Saldo financeiro restante do contrato (Valor Global - Valor Executado)."""
        return max(Decimal('0.00'), self.valor_global - self.valor_executado)

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

    def excluir_com_dependencias(self):
        """Apaga o contrato junto com todo o histórico derivado que hoje pode manter referências protegidas."""

        with transaction.atomic():
            # A avaliação mensal referencia o formulário-base com PROTECT, então o histórico
            # de competências precisa sair antes de removermos os formulários estruturais.
            self.competencias.all().delete()
            # Depois disso os formulários não têm mais avaliações mensais protegendo sua exclusão.
            self.formularios_avaliacao.all().delete()
            # O restante das dependências segue por cascata nativa do modelo.
            self.delete()

    def usuario_pode_gerir(self, user):
        return usuario_pode_gerir_contrato_v2(user, self)

    def usuario_pode_preencher_checklist(self, user):
        return usuario_pode_preencher_checklist_v2(user, self)

    def usuario_pode_preencher_avaliacao(self, user):
        return usuario_pode_preencher_avaliacao_v2(user, self)

    def usuario_pode_preencher_medicao(self, user):
        return usuario_pode_preencher_medicao_v2(user, self)

    @property
    def possui_processos_sei_completos(self):
        """Centraliza a checagem usada no formulário e antes da geração das competências."""

        return all(
            (
                self.processo_sei_gestao_numero or '',
                self.processo_sei_gestao_url or '',
                self.processo_sei_execucao_numero or '',
                self.processo_sei_execucao_url or '',
            )
        )

    @property
    def responsavel_empresa_principal(self):
        """Entrega o primeiro responsável ativo da contratada para exibição resumida."""

        return self.empresa_contratada.responsaveis.filter(ativo=True).order_by('nome', 'id').first()


class ContratoItem(models.Model):
    """Item financeiro do contrato usado para formar a base mensal e o valor global."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='itens')
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

    @property
    def quantidade_acumulada(self):
        return (self.quantidade or Decimal('0.00')) * Decimal(self.contrato.vigencia_total_meses)

    @property
    def quantidade_executada(self):
        total = self.medicoes.filter(competencia__medicao_concluida_em__isnull=False).aggregate(total=Sum('quantidade')).get('total') or Decimal('0.00')
        return total

    @property
    def quantidade_disponivel(self):
        return self.quantidade_acumulada - self.quantidade_executada

    def save(self, *args, **kwargs):
        """Recalcula o subtotal no backend para evitar divergência entre tela e banco."""

        self.valor_subtotal = quantize_money((self.quantidade or Decimal('0.00')) * (self.valor_unitario or Decimal('0.00')))
        super().save(*args, **kwargs)
        self.contrato.refresh_financials()

    def delete(self, *args, **kwargs):
        contrato = self.contrato
        super().delete(*args, **kwargs)
        contrato.refresh_financials()


class DocumentoImportanteContrato(models.Model):
    """Armazena anexos institucionais do contrato fora do fluxo mensal de competências."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='documentos_importantes')
    nome = models.CharField('Nome', max_length=220)
    arquivo = models.FileField('Anexo', upload_to='contratos/documentos_importantes/')
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_importantes_contrato_criados',
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documentos_importantes_contrato_atualizados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Documento importante do contrato'
        verbose_name_plural = 'Documentos importantes do contrato'

    def __str__(self):
        return self.nome

    @property
    def inserido_por_display(self):
        """Entrega um texto resiliente para a coluna de autoria da tabela."""

        if not self.criado_por:
            return '-'
        perfil = getattr(self.criado_por, 'perfil', None)
        return getattr(perfil, 'nome_completo', None) or self.criado_por.get_full_name() or self.criado_por.username


class ChecklistModelo(models.Model):
    """Versão do checklist documental do contrato usada para replicar competências."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='checklist_modelos')
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
        # Quando o contrato ainda não tem checklist, a primeira versão precisa nascer ativa para não bloquear o fluxo.
        if not self.pk and not type(self).objects.filter(contrato=self.contrato).exists():
            self.ativo = True
        super().save(*args, **kwargs)
        if self.ativo:
            type(self).objects.filter(contrato=self.contrato).exclude(pk=self.pk).update(ativo=False)
            sincronizar_checklist_ativo_contrato_v2(self.contrato)


class ChecklistModeloItem(models.Model):
    """Documento exigido dentro de uma versão de checklist do contrato."""

    modelo = models.ForeignKey(ChecklistModelo, on_delete=models.CASCADE, related_name='itens')
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


class ChecklistPadraoGlobal(models.Model):
    """Cadastro global de versões padrão que podem ser clonadas para contratos específicos."""

    nome = models.CharField('Nome da versão', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    observacoes = models.TextField('Observações', blank=True)
    ativo = models.BooleanField('Ativo', default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checklists_padrao_globais_criados',
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='checklists_padrao_globais_atualizados',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-ativo', '-atualizado_em', '-id']
        verbose_name = 'Checklist padrão global'
        verbose_name_plural = 'Checklists padrão globais'

    def __str__(self):
        return self.nome

    @property
    def atualizado_por_display(self):
        """Entrega um rótulo amigável para a coluna de autoria da listagem administrativa."""

        if not self.atualizado_por:
            return '-'
        perfil = getattr(self.atualizado_por, 'perfil', None)
        return getattr(perfil, 'nome_completo', None) or self.atualizado_por.get_full_name() or self.atualizado_por.username

    def save(self, *args, **kwargs):
        # O primeiro checklist padrão global precisa nascer ativo para já ficar disponível para carga.
        if not self.pk and not type(self).objects.exists():
            self.ativo = True
        super().save(*args, **kwargs)
        if self.ativo:
            type(self).objects.exclude(pk=self.pk).update(ativo=False)


class ChecklistPadraoGlobalItem(models.Model):
    """Itens que compõem um checklist padrão global reutilizável entre contratos."""

    checklist_padrao = models.ForeignKey(ChecklistPadraoGlobal, on_delete=models.CASCADE, related_name='itens')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    titulo = models.CharField('Título', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    obrigatorio = models.BooleanField('Obrigatório', default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ordem', 'id']
        unique_together = [('checklist_padrao', 'ordem')]
        verbose_name = 'Item do checklist padrão global'
        verbose_name_plural = 'Itens do checklist padrão global'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if self.pk is None and not self.ordem:
            maior = type(self).objects.filter(checklist_padrao=self.checklist_padrao).aggregate(max_ordem=Max('ordem')).get('max_ordem') or 0
            self.ordem = maior + 1
        super().save(*args, **kwargs)


class FormularioAvaliacao(models.Model):
    """Versão do formulário de avaliação de qualidade do contrato."""

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='formularios_avaliacao')
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
        # O primeiro formulário do contrato precisa nascer ativo para evitar configuração inicial inconsistente.
        if not self.pk and not type(self).objects.filter(contrato=self.contrato).exists():
            self.ativo = True
        super().save(*args, **kwargs)
        if self.ativo:
            type(self).objects.filter(contrato=self.contrato).exclude(pk=self.pk).update(ativo=False)

    def delete(self, *args, **kwargs):
        if self.contrato.competencias.exists():
            raise ValidationError('Não é permitido excluir formulários de avaliação após a geração de competências.')
        super().delete(*args, **kwargs)


class EscalaNotaAvaliacao(models.Model):
    """Escala parametrizável de notas disponível para o formulário de avaliação."""

    formulario = models.ForeignKey(FormularioAvaliacao, on_delete=models.CASCADE, related_name='escalas')
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


class FaixaLiberacaoAvaliacao(models.Model):
    """Faixa de nota final usada para sugerir o percentual de liberação financeira."""

    formulario = models.ForeignKey(FormularioAvaliacao, on_delete=models.CASCADE, related_name='faixas_liberacao')
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


class GrupoAvaliacao(models.Model):
    """Grupo de itens de avaliação usado apenas para organizar visualmente o formulário."""

    formulario = models.ForeignKey(FormularioAvaliacao, on_delete=models.CASCADE, related_name='grupos')
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


class ItemAvaliacao(models.Model):
    """Item avaliável dentro de um grupo da versão de avaliação."""

    grupo = models.ForeignKey(GrupoAvaliacao, on_delete=models.CASCADE, related_name='itens')
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


class CompetenciaPagamento(models.Model):
    """Competência mensal única que concentra checklist, medição, avaliação e pagamento."""

    class Status(models.TextChoices):
        BLOQUEADA = 'BLOQUEADA', 'Bloqueada'
        MEDICAO_PENDENTE = 'MEDICAO_PENDENTE', 'Medição pendente'
        AVALIACAO_PENDENTE = 'AVALIACAO_PENDENTE', 'Avaliação pendente'
        CHECKLIST_PENDENTE = 'CHECKLIST_PENDENTE', 'Checklist pendente'
        DOWNLOAD_PENDENTE = 'DOWNLOAD_PENDENTE', 'Download pendente'
        OB_PENDENTE = 'OB_PENDENTE', 'Ordem bancária pendente'
        PAGA = 'PAGA', 'Paga'
        CANCELADA = 'CANCELADA', 'Cancelada'


    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='competencias')
    periodo_inicio = models.DateField('Período inicial')
    periodo_fim = models.DateField('Período final')
    status = models.CharField('Status', max_length=30, choices=Status.choices, default=Status.BLOQUEADA)
    aplicar_pro_rata = models.BooleanField('Aplicar pró-rata', default=False)
    valor_previsto = models.DecimalField('Valor previsto', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_medido = models.DecimalField('Valor medido', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_liberado_sugerido = models.DecimalField('Valor liberado sugerido', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    aceite_provisorio_arquivo = models.FileField('Comprovação do aceite provisório', upload_to='contratos/medicao/', blank=True)
    data_aceite_provisorio = models.DateField('Data do aceite provisório', null=True, blank=True)
    prazo_aceite_definitivo_dias = models.PositiveIntegerField('Prazo para aceite definitivo (dias corridos)', null=True, blank=True)
    aceite_definitivo_arquivo = models.FileField('Comprovação do aceite definitivo', upload_to='contratos/medicao/', blank=True)
    data_aceite_definitivo = models.DateField('Data do aceite definitivo', null=True, blank=True)
    prazo_pagamento_dias = models.PositiveIntegerField('Prazo para pagamento (dias corridos)', null=True, blank=True)
    numero_nota_fiscal = models.CharField('Número da nota fiscal', max_length=120, blank=True)
    valor_nota_fiscal = models.DecimalField('Valor da nota fiscal', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_ir = models.DecimalField('Retenção IR', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_inss = models.DecimalField('Retenção INSS', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_iss = models.DecimalField('Retenção ISS', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_pis_pasep = models.DecimalField('Retenção PIS/PASEP', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_cofins = models.DecimalField('Retenção COFINS', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_liberado_final = models.DecimalField('Valor liberado final', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    nota_adicional_arquivo = models.FileField('Nota Fiscal adicional', upload_to='contratos/pagamentos/', blank=True)
    numero_nota_adicional = models.CharField('Número da nota fiscal adicional', max_length=120, blank=True)
    valor_nota_adicional = models.DecimalField('Valor da nota fiscal adicional', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_ir_adicional = models.DecimalField('Retenção IR da nota adicional', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_inss_adicional = models.DecimalField('Retenção INSS da nota adicional', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_iss_adicional = models.DecimalField('Retenção ISS da nota adicional', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_pis_pasep_adicional = models.DecimalField('Retenção PIS/PASEP da nota adicional', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    retencao_cofins_adicional = models.DecimalField('Retenção COFINS da nota adicional', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_liquido_nota_adicional = models.DecimalField('Valor líquido da nota adicional', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    nota_adicional_nao_consta = models.BooleanField('Nota fiscal adicional não consta', default=False)
    gestor_pagamento = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_como_gestor_pagamento',
        verbose_name='Gestor do contrato',
    )
    gestor_pagamento_em_exercicio = models.BooleanField('Gestor do contrato em exercício', default=False)
    coordenadora_pagamento = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_como_coordenadora_pagamento',
        verbose_name='Coordenadora',
    )
    coordenadora_em_exercicio = models.BooleanField('Coordenadora em exercício', default=False)
    diretora_pagamento = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_como_diretora_pagamento',
        verbose_name='Diretora',
    )
    diretora_em_exercicio = models.BooleanField('Diretora em exercício', default=False)
    subsecretario_pagamento = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_como_subsecretario_pagamento',
        verbose_name='Subsecretário',
    )
    subsecretario_em_exercicio = models.BooleanField('Subsecretário em exercício', default=False)
    checklist_modelo_snapshot = models.JSONField('Snapshot do checklist', default=dict, blank=True)
    formulario_avaliacao_snapshot = models.JSONField('Snapshot da avaliação', default=dict, blank=True)
    checklist_concluido_em = models.DateTimeField('Checklist concluído em', null=True, blank=True)
    medicao_concluida_em = models.DateTimeField('Medição concluída em', null=True, blank=True)
    download_realizado_em = models.DateTimeField('Download realizado em', null=True, blank=True)
    data_pagamento = models.DateField('Data do pagamento', null=True, blank=True)
    nota_fiscal_fatura = models.FileField('Nota Fiscal/Fatura', upload_to='contratos/pagamentos/', blank=True)
    avaliacao_assinada = models.FileField('Avaliação de qualidade assinada', upload_to='contratos/avaliacoes/', blank=True)
    ordem_bancaria_arquivo = models.FileField('Ordem bancária', upload_to='contratos/pagamentos/', blank=True)
    atestado_realizacao = models.FileField('Atestado de Realização', upload_to='contratos/pagamentos/', blank=True)
    despacho_dof = models.FileField('Despacho DOF', upload_to='contratos/pagamentos/', blank=True)
    autorizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_autorizadas',
    )
    justificativa_divergencia = models.TextField('Justificativa de divergência', blank=True)
    observacoes_medicao = models.TextField('Observações finais da medição', blank=True)
    medicao_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_medicao_preenchidas',
        verbose_name='Medição preenchida por',
    )
    medicao_preenchida_em = models.DateTimeField('Medição preenchida em', null=True, blank=True)
    aceite_provisorio_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_aceite_provisorio_preenchidas',
        verbose_name='Aceite provisório preenchido por',
    )
    aceite_provisorio_preenchida_em = models.DateTimeField('Aceite provisório preenchido em', null=True, blank=True)
    aceite_definitivo_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_aceite_definitivo_preenchidas',
        verbose_name='Aceite definitivo preenchido por',
    )
    aceite_definitivo_preenchida_em = models.DateTimeField('Aceite definitivo preenchido em', null=True, blank=True)
    nota_principal_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_nota_principal_preenchidas',
        verbose_name='Nota principal preenchida por',
    )
    nota_principal_preenchida_em = models.DateTimeField('Nota principal preenchida em', null=True, blank=True)
    nota_adicional_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_nota_adicional_preenchidas',
        verbose_name='Nota adicional preenchida por',
    )
    nota_adicional_preenchida_em = models.DateTimeField('Nota adicional preenchida em', null=True, blank=True)
    observacoes_finais_preenchida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='competencias_v2_observacoes_finais_preenchidas',
        verbose_name='Observações finais preenchidas por',
    )
    observacoes_finais_preenchida_em = models.DateTimeField('Observações finais preenchidas em', null=True, blank=True)
    monitoramento_etapa = models.CharField('Etapa monitorada', max_length=80, blank=True)
    monitoramento_inicio = models.DateField('Data inicial do monitoramento', null=True, blank=True)
    monitoramento_limite = models.DateField('Data limite do monitoramento', null=True, blank=True)
    alerta_50_enviado_em = models.DateField('Alerta de 50% enviado em', null=True, blank=True)
    alerta_75_ultimo_envio_em = models.DateField('Último alerta diário enviado em', null=True, blank=True)
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
    def status_marcador(self):
        """Personaliza o texto do selo da competência sem mexer nas labels institucionais do campo."""

        if self.status == self.Status.PAGA and self.data_pagamento:
            return f'Paga - {self.data_pagamento:%d/%m/%Y}'
        return self.get_status_display()

    @property
    def exige_avaliacao(self):
        return bool(self.formulario_avaliacao_snapshot)

    @property
    def possui_nota_adicional(self):
        return bool(self.nota_adicional_arquivo or self.numero_nota_adicional or self.valor_nota_adicional)

    @property
    def nota_adicional_resolvida(self):
        """Indica se a competência já definiu a situação da nota adicional."""

        return bool(self.nota_adicional_nao_consta or self.possui_nota_adicional)

    @property
    def medicao_tem_conteudo(self):
        """Indica se a seção de medição já recebeu algum preenchimento operacional."""

        return bool(self.aplicar_pro_rata or self.medicoes.filter(quantidade__gt=0).exists())

    @property
    def aceite_provisorio_tem_conteudo(self):
        """Agrupa os dados do bloco de aceite provisório para auditoria e exibição."""

        return bool(self.aceite_provisorio_arquivo or self.data_aceite_provisorio or self.prazo_aceite_definitivo_dias)

    @property
    def aceite_definitivo_tem_conteudo(self):
        """Agrupa os dados do bloco de aceite definitivo para auditoria e exibição."""

        return bool(self.aceite_definitivo_arquivo or self.data_aceite_definitivo or self.prazo_pagamento_dias)

    @property
    def nota_principal_tem_conteudo(self):
        """Identifica se o bloco da nota principal já começou a ser preenchido."""

        return any(
            [
                bool(self.nota_fiscal_fatura),
                bool((self.numero_nota_fiscal or '').strip()),
                (self.valor_nota_fiscal or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_ir or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_inss or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_iss or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_pis_pasep or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_cofins or Decimal('0.00')) > Decimal('0.00'),
            ]
        )

    @property
    def nota_adicional_tem_conteudo(self):
        """Identifica se o bloco da nota adicional já começou a ser preenchido."""

        return any(
            [
                bool(self.nota_adicional_nao_consta),
                bool(self.nota_adicional_arquivo),
                bool((self.numero_nota_adicional or '').strip()),
                (self.valor_nota_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_ir_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_inss_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_iss_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_pis_pasep_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_cofins_adicional or Decimal('0.00')) > Decimal('0.00'),
            ]
        )

    @property
    def observacoes_finais_tem_conteudo(self):
        """Resume se o texto final da medição já foi registrado."""

        return bool((self.observacoes_medicao or '').strip())

    @property
    def total_retencoes(self):
        """Consolida as retenções informadas no fechamento financeiro da competência."""

        return (
            (self.retencao_ir or Decimal('0.00'))
            + (self.retencao_inss or Decimal('0.00'))
            + (self.retencao_iss or Decimal('0.00'))
            + (self.retencao_pis_pasep or Decimal('0.00'))
            + (self.retencao_cofins or Decimal('0.00'))
        )

    @property
    def total_retencoes_adicionais(self):
        """Consolida as retenções da nota adicional quando ela existir."""

        return (
            (self.retencao_ir_adicional or Decimal('0.00'))
            + (self.retencao_inss_adicional or Decimal('0.00'))
            + (self.retencao_iss_adicional or Decimal('0.00'))
            + (self.retencao_pis_pasep_adicional or Decimal('0.00'))
            + (self.retencao_cofins_adicional or Decimal('0.00'))
        )

    @property
    def avaliacao_qualidade_segura(self):
        try:
            return self.avaliacao_qualidade
        except AvaliacaoQualidadeCompetencia.DoesNotExist:
            return None

    @property
    def checklist_estado(self):
        """Estado visual do botão de checklist no card da competência."""

        if not self.checklist_itens.filter(obrigatorio=True, concluido=False).exists() and self.checklist_itens.exists():
            return 'done'
        # Em andamento se pelo menos um item foi concluído ou tem anexo
        if self.checklist_itens.filter(Q(concluido=True) | Q(anexo__isnull=False)).exists():
            return 'pending'
        return 'idle'

    @property
    def medicao_estado(self):
        """Estado visual do botão de medição no card da competência."""

        if self.medicao_concluida_em:
            return 'done'
        # A etapa fica amarela assim que qualquer parte operacional da medição começar,
        # mesmo antes da conclusão completa com aceites, NF e retenções.
        if self.medicao_iniciada:
            return 'pending'
        return 'idle'

    @property
    def medicao_iniciada(self):
        """Sinaliza progresso parcial da medição expandida para o estado visual do card."""

        return any(
            [
                self.medicoes.filter(quantidade__gt=0).exists(),
                bool(self.aceite_provisorio_arquivo),
                bool(self.data_aceite_provisorio),
                bool(self.prazo_aceite_definitivo_dias),
                bool(self.aceite_definitivo_arquivo),
                bool(self.data_aceite_definitivo),
                bool(self.prazo_pagamento_dias),
                bool(self.nota_fiscal_fatura),
                bool((self.numero_nota_fiscal or '').strip()),
                (self.valor_nota_fiscal or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_ir or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_inss or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_iss or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_pis_pasep or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_cofins or Decimal('0.00')) > Decimal('0.00'),
                bool(self.nota_adicional_arquivo),
                bool((self.numero_nota_adicional or '').strip()),
                (self.valor_nota_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_ir_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_inss_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_iss_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_pis_pasep_adicional or Decimal('0.00')) > Decimal('0.00'),
                (self.retencao_cofins_adicional or Decimal('0.00')) > Decimal('0.00'),
                bool((self.observacoes_medicao or '').strip()),
            ]
        )

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
    def download_estado(self):
        """Estado visual do botão de download no card da competência."""

        if self.download_realizado_em:
            return 'done'
        if self.status in {self.Status.DOWNLOAD_PENDENTE, self.Status.OB_PENDENTE, self.Status.PAGA}:
            return 'pending'
        return 'idle'

    @property
    def ob_estado(self):
        """Estado visual da etapa final de ordem bancária."""

        if self.status == self.Status.PAGA and self.ordem_bancaria_arquivo and self.data_pagamento:
            return 'done'
        if self.status in {self.Status.OB_PENDENTE, self.Status.PAGA} or self.ordem_bancaria_arquivo or self.data_pagamento:
            return 'pending'
        return 'idle'

    @property
    def medicao_disponivel(self):
        """A medição é a porta de entrada da competência e permanece sempre acessível."""

        return self.status not in {self.Status.CANCELADA}

    @property
    def avaliacao_disponivel(self):
        """Libera a avaliação apenas após a conclusão formal da medição."""

        return bool(self.exige_avaliacao and self.medicao_concluida_em)

    @property
    def checklist_disponivel(self):
        """Checklist só pode ser aberto após medição e, quando exigida, avaliação."""

        if not self.medicao_concluida_em:
            return False
        if self.exige_avaliacao and not getattr(self.avaliacao_qualidade_segura, 'concluida_em', None):
            return False
        return True

    @property
    def download_disponivel(self):
        """Download é liberado somente quando o checklist da competência estiver concluído."""

        return bool(self.checklist_concluido_em or self.status in {self.Status.DOWNLOAD_PENDENTE, self.Status.OB_PENDENTE, self.Status.PAGA})

    @property
    def ob_disponivel(self):
        """A Ordem Bancária só entra no fluxo depois da geração do pacote documental."""

        return bool(self.download_realizado_em or self.status in {self.Status.OB_PENDENTE, self.Status.PAGA})

    @property
    def monitoramento_percentual(self):
        """Calcula o percentual temporal consumido da etapa monitorada."""

        if not self.monitoramento_inicio or not self.monitoramento_limite:
            return 0
        hoje = timezone.localdate()
        if hoje <= self.monitoramento_inicio:
            return 0
        if hoje >= self.monitoramento_limite:
            return 100
        total = (self.monitoramento_limite - self.monitoramento_inicio).days
        if total <= 0:
            return 100
        decorrido = (hoje - self.monitoramento_inicio).days
        return min(max(int((decorrido / total) * 100), 0), 100)

    @property
    def monitoramento_cor(self):
        """Entrega a cor da barra de prazo da competência."""

        percentual = self.monitoramento_percentual
        if percentual <= 50:
            return 'success'
        if percentual <= 75:
            return 'warning'
        return 'danger'

    @property
    def monitoramento_ativo(self):
        """Indica se a competência ainda está sob contagem visual de prazo."""

        return bool(self.monitoramento_etapa and self.monitoramento_inicio and self.monitoramento_limite)

    @property
    def monitoramento_fundo_classe(self):
        """Entrega a classe visual do card conforme a mesma cor da barra, em tom claro."""

        if not self.monitoramento_ativo:
            return ''
        return f'contratos-competencia-card--{self.monitoramento_cor}'

    @property
    def monitoramento_marcos(self):
        """Monta marcadores diários para a barra da competência, espelhando o padrão da vigência."""

        if not self.monitoramento_ativo:
            return []

        inicio = self.monitoramento_inicio
        limite = self.monitoramento_limite
        hoje = timezone.localdate()
        total_dias = max((limite - inicio).days, 0)
        marcos = []

        for indice in range(total_dias + 1):
            data_marco = inicio + timedelta(days=indice)
            percentual = (indice / total_dias * 100) if total_dias > 0 else 0
            marcos.append(
                {
                    'data': data_marco,
                    'percentual_posicao': f'{percentual:.2f}',
                    'passado': data_marco < hoje,
                    'atual': data_marco == hoje,
                    'inicial': indice == 0,
                    'final': indice == total_dias,
                }
            )
        return marcos

    def obter_assinatura_pagamento(self, usuario, cargo, em_exercicio=False):
        """Entrega os textos da assinatura conforme a regra de cargo normal ou em exercício."""

        if not usuario:
            return {'nome': '-', 'cargo': f'{cargo} - em exercício' if em_exercicio else cargo}
        nome = usuario.get_full_name() or usuario.username
        return {
            'nome': nome,
            'cargo': f'{cargo} - em exercício' if em_exercicio else cargo,
        }

    @property
    def etapas(self):
        """Mantém a estrutura textual para usos internos e testes existentes."""

        return [
            ('Medição', self.medicao_estado),
            ('Avaliação', self.avaliacao_estado),
            ('Checklist', self.checklist_estado),
            ('Download', self.download_estado),
            ('Ordem Bancária', self.ob_estado),
        ]

    def save(self, *args, **kwargs):
        if not self.valor_previsto:
            self.valor_previsto = self.contrato.base_mensal
        super().save(*args, **kwargs)


# Os aliases abaixo preservam comparações legadas durante a transição do fluxo antigo.
CompetenciaPagamento.Status.PAGAMENTO_PENDENTE = CompetenciaPagamento.Status.DOWNLOAD_PENDENTE
CompetenciaPagamento.Status.PAGAMENTO_REGISTRADO = CompetenciaPagamento.Status.OB_PENDENTE


class ExportacaoDocumentosCompetencia(models.Model):
    """Controla a geração assíncrona do PDF consolidado de uma competência."""

    class Status(models.TextChoices):
        PENDENTE = 'PENDENTE', 'Pendente'
        PROCESSANDO = 'PROCESSANDO', 'Processando'
        CONCLUIDO = 'CONCLUIDO', 'Concluído'
        ERRO = 'ERRO', 'Erro'

    competencia = models.ForeignKey(CompetenciaPagamento, on_delete=models.CASCADE, related_name='exportacoes_documentos')
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='exportacoes_documentos_competencia',
    )
    status = models.CharField('Status', max_length=20, choices=Status.choices, default=Status.PENDENTE)
    etapa_atual = models.CharField('Etapa atual', max_length=120, blank=True)
    percentual = models.PositiveSmallIntegerField('Percentual', default=0)
    mensagem = models.CharField('Mensagem', max_length=255, blank=True)
    tipo_saida = models.CharField('Tipo de saída', max_length=20, default='unificado')
    arquivo_pdf = models.FileField('Arquivo PDF consolidado', upload_to='contratos/downloads/', blank=True)
    erro_detalhe = models.TextField('Detalhes do erro', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    concluido_em = models.DateTimeField('Concluído em', null=True, blank=True)

    class Meta:
        ordering = ['-criado_em', '-id']
        verbose_name = 'Exportação de documentos da competência'
        verbose_name_plural = 'Exportações de documentos das competências'

    def __str__(self):
        return f'Exportação {self.competencia_id} - {self.solicitado_por_id} - {self.status}'


class ChecklistCompetenciaItem(models.Model):
    """Snapshot documental que o fiscal precisa entregar dentro da competência."""

    class Categoria(models.TextChoices):
        OFICIAL = 'OFICIAL', 'Oficial'
        NOTA_ADICIONAL = 'NOTA_ADICIONAL', 'Nota adicional'

    competencia = models.ForeignKey(CompetenciaPagamento, on_delete=models.CASCADE, related_name='checklist_itens')
    ordem = models.PositiveIntegerField('Ordem', default=1)
    titulo = models.CharField('Título', max_length=180)
    descricao = models.TextField('Descrição', blank=True)
    categoria = models.CharField('Categoria do item', max_length=20, choices=Categoria.choices, default=Categoria.OFICIAL)
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


class ChecklistCompetenciaAnexo(models.Model):
    """Arquivo principal anexado ao item de checklist da competência."""

    item = models.OneToOneField(ChecklistCompetenciaItem, on_delete=models.CASCADE, related_name='anexo')
    arquivo = models.FileField('Arquivo', upload_to='contratos/checklists/')
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


class MedicaoItemCompetencia(models.Model):
    """Quantidade medida por item do contrato dentro de uma competência mensal."""

    competencia = models.ForeignKey(CompetenciaPagamento, on_delete=models.CASCADE, related_name='medicoes')
    item_contrato = models.ForeignKey(ContratoItem, on_delete=models.CASCADE, related_name='medicoes')
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


class AvaliacaoQualidadeCompetencia(models.Model):
    """Avaliação efetiva aplicada a uma competência quando o contrato exige essa etapa."""

    competencia = models.OneToOneField(CompetenciaPagamento, on_delete=models.CASCADE, related_name='avaliacao_qualidade')
    formulario = models.ForeignKey(FormularioAvaliacao, on_delete=models.PROTECT, related_name='avaliacoes')
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

    avaliacao = models.ForeignKey(AvaliacaoQualidadeCompetencia, on_delete=models.CASCADE, related_name='itens')
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


class PrazoMonitoramento(models.Model):
    """
    Guarda os prazos de certidões, planos de ação e outros itens de monitoramento
    associados a um Contrato que já possui competências geradas.
    """
    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='prazos',
        verbose_name='Contrato'
    )
    nome = models.CharField('Nome', max_length=255)
    data_inicio = models.DateField('Data de início', blank=True, null=True)
    data_limite = models.DateField('Data limite')
    anexo = models.FileField('Anexo', upload_to='contratos/prazos/', blank=True, null=True)
    concluido = models.BooleanField('Concluído', default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['concluido', 'data_limite', 'criado_em']
        verbose_name = 'Prazo de monitoramento'
        verbose_name_plural = 'Prazos de monitoramento'

    def __str__(self):
        return f'{self.nome} - {self.data_limite}'

    @property
    def percentual_decorrido(self):
        """
        Retorna o percentual decorrido do prazo (evolução temporal).
        Calculado a partir da data de início configurada ou, na ausência dela,
        a partir da data de criação do registro para preservar compatibilidade.
        """
        if self.concluido:
            return 100

        today = timezone.localdate()
        # Para prazos legados, o cadastro continua sendo o marco inicial.
        data_inicio = self.data_inicio or (self.criado_em.date() if self.criado_em else today)

        if today >= self.data_limite:
            return 100
        if today <= data_inicio:
            return 0

        total_days = (self.data_limite - data_inicio).days
        passed_days = (today - data_inicio).days

        if total_days <= 0:
            return 100

        return min(max(int((passed_days / total_days) * 100), 0), 100)

    @property
    def cor_classe(self):
        """
        Retorna a classe do Bootstrap / CSS associada à criticidade do prazo:
        - Até 50%: success (Verde)
        - 51% a 75%: warning (Amarelo)
        - Acima de 75%: danger (Vermelho)
        """
        pct = self.percentual_decorrido
        if pct <= 50:
            return 'success'
        elif pct <= 75:
            return 'warning'
        else:
            return 'danger'
