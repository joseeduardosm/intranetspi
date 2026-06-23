# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Definir formulários do Contratos V2 incluindo checklist, avaliação, medição e pagamento.

import re
from decimal import Decimal
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from pypdf import PdfReader

def validar_upload_pdf(arquivo):
    """Confere extensão, content-type e estrutura mínima do PDF enviado."""

    if not arquivo:
        return arquivo
    nome = (getattr(arquivo, 'name', '') or '').lower()
    content_type = (getattr(arquivo, 'content_type', '') or '').lower()
    if not nome.endswith('.pdf') or content_type not in {'application/pdf', 'application/x-pdf'}:
        raise ValidationError('Envie um arquivo PDF válido.')
    posicao_inicial = arquivo.tell() if hasattr(arquivo, 'tell') else None
    try:
        if hasattr(arquivo, 'seek'):
            arquivo.seek(0)
        PdfReader(BytesIO(arquivo.read()), strict=False)
    except Exception as exc:
        raise ValidationError('O arquivo enviado não é um PDF válido ou está corrompido.') from exc
    finally:
        if hasattr(arquivo, 'seek'):
            arquivo.seek(0 if posicao_inicial is None else posicao_inicial)
    return arquivo

from contratos.services import inclusive_end_date

from .models import (
    AvaliacaoQualidadeCompetencia,
    ChecklistCompetenciaItem,
    ChecklistModeloItem,
    ChecklistModelo,
    ChecklistPadraoGlobal,
    ChecklistPadraoGlobalItem,
    CompetenciaPagamento,
    ContratoItem,
    Contrato,
    DocumentoImportanteContrato,
    EscalaNotaAvaliacao,
    FaixaLiberacaoAvaliacao,
    FormularioAvaliacao,
    FormularioAvaliacaoPadraoGlobal,
    GrupoAvaliacao,
    GrupoAvaliacaoPadraoGlobal,
    ItemAvaliacao,
    ItemAvaliacaoPadraoGlobal,
    MedicaoItemCompetencia,
    EmpresaContratada,
    ResponsavelEmpresa,
    PrazoMonitoramento,
    EscalaNotaAvaliacaoPadraoGlobal,
    FaixaLiberacaoAvaliacaoPadraoGlobal,
)


User = get_user_model()
BOOTSTRAP_INPUT = 'form-control form-control-lg'
BOOTSTRAP_TEXTAREA = 'form-control spi-textarea-compact'
NUMERO_CONTRATO_RE = re.compile(r'^\d{3}/\d{4}$')
HTML5_DATE_FORMAT = '%Y-%m-%d'


def html5_date_input(extra_attrs=None):
    """Padroniza campos de data HTML5 para renderizar e ler datas no formato ISO."""

    attrs = {'type': 'date'}
    if extra_attrs:
        attrs.update(extra_attrs)
    return forms.DateInput(format=HTML5_DATE_FORMAT, attrs=attrs)


def parse_numero_contrato(value):
    """Valida e separa o número do contrato no formato NNN/AAAA."""

    normalizado = (value or '').strip()
    if not NUMERO_CONTRATO_RE.match(normalizado):
        return None
    numero, ano = normalizado.split('/')
    return int(numero), int(ano)


def numero_contrato_por_ano(ano):
    """Gera o próximo número sequencial considerando apenas contratos da V2."""

    maior = 0
    suffix = f'/{ano}'
    for numero in Contrato.objects.filter(numero_contrato__endswith=suffix).values_list('numero_contrato', flat=True):
        parsed = parse_numero_contrato(numero)
        if parsed and parsed[1] == ano:
            maior = max(maior, parsed[0])
    return f'{maior + 1:03d}/{ano}'


def calcular_percentual_por_faixa(snapshot_faixas, nota_final):
    """Replica a regra de faixas para sugerir o percentual a partir de uma nota informada."""

    nota_decimal = Decimal(nota_final or Decimal('0.00'))
    percentual = Decimal('100.00')
    for faixa in snapshot_faixas or []:
        nota_minima = Decimal(faixa['nota_minima'])
        nota_maxima = Decimal(faixa['nota_maxima']) if faixa.get('nota_maxima') not in {'', None} else None
        if nota_decimal < nota_minima:
            continue
        if nota_maxima is not None and nota_decimal > nota_maxima:
            continue
        percentual = Decimal(faixa['percentual_liberacao'])
        break
    return percentual


def calcular_valor_avaliacao_sugerido(competencia, percentual):
    """Calcula o valor a pagar na avaliação com base no percentual e na nota fiscal da competência."""

    base = Decimal(getattr(competencia, 'valor_nota_fiscal', Decimal('0.00')) or Decimal('0.00'))
    return base * (Decimal(percentual or Decimal('0.00')) / Decimal('100.00'))


class BootstrapModelForm(forms.ModelForm):
    """Aplica o padrão visual do projeto aos widgets do módulo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = 'form-select form-select-lg'
            elif isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(field.widget, forms.Textarea):
                css = BOOTSTRAP_TEXTAREA
            elif isinstance(field.widget, forms.ClearableFileInput):
                css = 'form-control'
            else:
                css = BOOTSTRAP_INPUT
            atual = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{atual} {css}'.strip()


class UsuarioPerfilChoiceField(forms.ModelChoiceField):
    """Mostra nome e login do usuário para facilitar a escolha dos responsáveis."""

    def label_from_instance(self, obj):
        perfil = getattr(obj, 'perfil', None)
        nome = perfil.nome_completo if perfil and perfil.nome_completo else obj.get_full_name() or obj.username
        return f'{nome} ({obj.username})'


class ContratoForm(BootstrapModelForm):
    numero_contrato_incremental = forms.BooleanField(
        label='Preencher número automaticamente',
        required=False,
        initial=True,
        help_text='Gera o próximo número disponível no formato NNN/AAAA conforme o ano da vigência.',
    )

    class Meta:
        model = Contrato
        fields = [
            'numero_contrato',
            'empresa_contratada',
            'apelido',
            'objeto',
            'data_inicio_vigencia',
            'prazo_inicial_meses',
            'vigencia_maxima_meses',
            'mes_reajuste',
            'processo_sei_gestao_numero',
            'processo_sei_gestao_url',
            'processo_sei_execucao_numero',
            'processo_sei_execucao_url',
            'fiscal_administrativo',
            'fiscal_administrativo_suplente',
            'fiscal_tecnico',
            'fiscal_tecnico_suplente',
            'gestor_contrato',
            'gestor_contrato_suplente',
            'situacao_forcada',
        ]

    def _incremental_requested(self):
        if self.is_bound:
            return self.data.get('numero_contrato_incremental') in {'on', 'true', 'True', '1'}
        return bool(self.fields['numero_contrato_incremental'].initial)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = User.objects.filter(is_active=True).select_related('perfil').order_by('perfil__nome_completo', 'username')
        user_field = UsuarioPerfilChoiceField(queryset=queryset)
        for name in (
            'fiscal_administrativo',
            'fiscal_administrativo_suplente',
            'fiscal_tecnico',
            'fiscal_tecnico_suplente',
            'gestor_contrato',
            'gestor_contrato_suplente',
        ):
            self.fields[name] = user_field.__class__(queryset=queryset, label=self.fields[name].label)
            self.fields[name].widget.attrs['class'] = 'form-select form-select-lg'
            self.fields[name].required = False
            self.fields[name].label = f'{self.fields[name].label} (Opcional)'

        # Os processos SEI são pré-condição do fluxo de competências e precisam ficar claros já no cadastro.
        self.fields['processo_sei_gestao_numero'].help_text = 'Informe o número do processo SEI de gestão.'
        self.fields['processo_sei_gestao_url'].help_text = 'Informe o link direto do processo SEI de gestão.'
        self.fields['processo_sei_execucao_numero'].help_text = 'Informe o número do processo SEI de execução.'
        self.fields['processo_sei_execucao_url'].help_text = 'Informe o link direto do processo SEI de execução.'

        if self.instance and self.instance.pk:
            self.fields['numero_contrato_incremental'].initial = False
        else:
            self.fields['numero_contrato'].required = False
            ano_inicial = timezone.localdate().year
            self.fields['numero_contrato'].initial = numero_contrato_por_ano(ano_inicial)
            self.fields['numero_contrato'].help_text = 'Formato: NNN/AAAA. Exemplo: 001/2026.'

    def clean_numero_contrato(self):
        numero = (self.cleaned_data.get('numero_contrato') or '').strip()
        incremental = self._incremental_requested()
        if incremental and not (self.instance and self.instance.pk):
            return numero
        if not parse_numero_contrato(numero):
            raise ValidationError('Use o formato NNN/AAAA. Exemplo: 001/2026.')
        return numero

    def clean(self):
        cleaned = super().clean()
        incremental = self._incremental_requested()
        data_inicio = cleaned.get('data_inicio_vigencia')

        if incremental and not (self.instance and self.instance.pk):
            ano = data_inicio.year if data_inicio else timezone.localdate().year
            cleaned['numero_contrato'] = numero_contrato_por_ano(ano)
            self.cleaned_data['numero_contrato'] = cleaned['numero_contrato']

        prazo_inicial = cleaned.get('prazo_inicial_meses') or 0
        vigencia_maxima = cleaned.get('vigencia_maxima_meses') or 0
        if prazo_inicial and vigencia_maxima and prazo_inicial > vigencia_maxima:
            self.add_error('vigencia_maxima_meses', 'A vigência máxima deve ser maior ou igual ao prazo inicial.')

        for field_name in (
            'processo_sei_gestao_numero',
            'processo_sei_gestao_url',
            'processo_sei_execucao_numero',
            'processo_sei_execucao_url',
        ):
            valor = cleaned.get(field_name)
            if isinstance(valor, str):
                valor = valor.strip()
                cleaned[field_name] = valor
            if not valor:
                self.add_error(field_name, 'Este campo é obrigatório.')

        return cleaned


class ContratoItemForm(BootstrapModelForm):
    """Formulário enxuto para itens financeiros que alimentam os totais do contrato."""

    class Meta:
        model = ContratoItem
        fields = ['ordem', 'descricao', 'codigo_siafisico', 'codigo_catmat_catser', 'quantidade', 'valor_unitario']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ordem'].required = False
        self.fields['ordem'].help_text = 'Se deixar em branco, o sistema usará o próximo número disponível.'
        # No cadastro operacional do contrato, o usuário informa a referência mensal do item.
        self.fields['quantidade'].label = 'Quantidade mensal'


class DocumentoImportanteContratoForm(BootstrapModelForm):
    """Mantém o cadastro de documentos importantes simples e direto."""

    class Meta:
        model = DocumentoImportanteContrato
        fields = ['nome', 'arquivo']


class ChecklistModeloForm(BootstrapModelForm):
    class Meta:
        model = ChecklistModelo
        fields = ['nome', 'descricao', 'observacoes', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class ChecklistModeloItemForm(BootstrapModelForm):
    class Meta:
        model = ChecklistModeloItem
        fields = ['ordem', 'titulo', 'descricao', 'obrigatorio']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ordem'].required = False
        self.fields['ordem'].help_text = 'Se deixar em branco, o sistema usará a próxima ordem disponível.'


class ChecklistPadraoGlobalForm(BootstrapModelForm):
    """Repete o formulário de checklist, agora desacoplado de um contrato específico."""

    class Meta:
        model = ChecklistPadraoGlobal
        fields = ['nome', 'descricao', 'observacoes', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class ChecklistPadraoGlobalItemForm(BootstrapModelForm):
    """Mantém o cadastro de itens do checklist padrão alinhado ao fluxo do checklist do contrato."""

    class Meta:
        model = ChecklistPadraoGlobalItem
        fields = ['ordem', 'titulo', 'descricao', 'obrigatorio']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ordem'].required = False
        self.fields['ordem'].help_text = 'Se deixar em branco, o sistema usará a próxima ordem disponível.'


class FormularioAvaliacaoForm(BootstrapModelForm):
    class Meta:
        model = FormularioAvaliacao
        fields = ['nome', 'descricao', 'ativo', 'observacoes']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class FormularioAvaliacaoPadraoGlobalForm(BootstrapModelForm):
    """Repete o formulário de avaliação, agora desacoplado de um contrato específico."""

    class Meta:
        model = FormularioAvaliacaoPadraoGlobal
        fields = ['nome', 'descricao', 'ativo', 'observacoes']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class EscalaNotaAvaliacaoForm(BootstrapModelForm):
    class Meta:
        model = EscalaNotaAvaliacao
        fields = ['valor', 'legenda']


class EscalaNotaAvaliacaoPadraoGlobalForm(BootstrapModelForm):
    """Mantém a escala padrão global alinhada ao cadastro da avaliação por contrato."""

    class Meta:
        model = EscalaNotaAvaliacaoPadraoGlobal
        fields = ['valor', 'legenda']


class FaixaLiberacaoAvaliacaoForm(BootstrapModelForm):
    class Meta:
        model = FaixaLiberacaoAvaliacao
        fields = ['nota_minima', 'nota_maxima', 'percentual_liberacao']


class FaixaLiberacaoAvaliacaoPadraoGlobalForm(BootstrapModelForm):
    """Replica as faixas de liberação para o cadastro padrão institucional."""

    class Meta:
        model = FaixaLiberacaoAvaliacaoPadraoGlobal
        fields = ['nota_minima', 'nota_maxima', 'percentual_liberacao']


class GrupoAvaliacaoForm(BootstrapModelForm):
    class Meta:
        model = GrupoAvaliacao
        fields = ['nome', 'descricao']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


class GrupoAvaliacaoPadraoGlobalForm(BootstrapModelForm):
    """Organiza os grupos do formulário padrão global com o mesmo desenho do contrato."""

    class Meta:
        model = GrupoAvaliacaoPadraoGlobal
        fields = ['nome', 'descricao']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


class ItemAvaliacaoForm(BootstrapModelForm):
    """Mantém o cadastro do item focado no conteúdo, com ordem controlada pelo sistema."""

    class Meta:
        model = ItemAvaliacao
        fields = ['descricao', 'peso_percentual', 'observacoes_padrao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes_padrao': forms.Textarea(attrs={'rows': 2}),
        }


class ItemAvaliacaoPadraoGlobalForm(BootstrapModelForm):
    """Mantém o item padrão global focado no conteúdo para clonagem futura."""

    class Meta:
        model = ItemAvaliacaoPadraoGlobal
        fields = ['descricao', 'peso_percentual', 'observacoes_padrao']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes_padrao': forms.Textarea(attrs={'rows': 2}),
        }


class CompetenciaChecklistUploadForm(forms.Form):
    """Tela dinâmica que recebe um arquivo por item do checklist da competência."""

    def __init__(self, *args, competencia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.competencia = competencia
        self.itens = list(competencia.checklist_itens.order_by('ordem', 'id') if competencia is not None else [])
        for item in self.itens:
            self.fields[f'arquivo_{item.pk}'] = forms.FileField(
                label=item.titulo,
                required=False,
                widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'application/pdf,.pdf'}),
            )
            self.fields[f'limpar_{item.pk}'] = forms.BooleanField(
                label='Remover arquivo atual',
                required=False,
            )

    def clean(self):
        cleaned = super().clean()
        for item in self.itens:
            arquivo = cleaned.get(f'arquivo_{item.pk}')
            if arquivo:
                cleaned[f'arquivo_{item.pk}'] = validar_upload_pdf(arquivo)
        return cleaned


class CompetenciaMedicaoLoteV2Form(forms.Form):
    """Monta a tabela mensal de medição trazendo automaticamente os itens do contrato V2."""

    ORIGEM_VALOR_NOTA_MEDICAO = 'medicao'
    ORIGEM_VALOR_NOTA_MANUAL = 'manual'

    CAMPOS_NOTA_PRINCIPAL = (
        'aceite_definitivo_arquivo',
        'data_aceite_definitivo',
        'prazo_pagamento_dias',
        'nota_fiscal_fatura',
        'numero_nota_fiscal',
        'valor_nota_fiscal',
        'retencao_ir',
        'retencao_inss',
        'retencao_iss',
        'retencao_pis_pasep',
        'retencao_cofins',
        'valor_liberado_final',
    )
    CAMPOS_NOTA_ADICIONAL = (
        'nota_adicional_arquivo',
        'nota_adicional_nao_consta',
        'numero_nota_adicional',
        'valor_nota_adicional',
        'retencao_ir_adicional',
        'retencao_inss_adicional',
        'retencao_iss_adicional',
        'retencao_pis_pasep_adicional',
        'retencao_cofins_adicional',
        'valor_liquido_nota_adicional',
    )

    def __init__(self, *args, contrato=None, competencia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contrato = contrato
        self.competencia = competencia
        self.valor_medido_referencia = Decimal(getattr(competencia, 'valor_medido', Decimal('0.00')) or Decimal('0.00'))
        self.itens = list((contrato.itens.order_by('ordem', 'id') if contrato is not None else []))
        self.permite_pro_rata = self._permite_pro_rata()
        medicoes_existentes = {}
        if competencia is not None:
            medicoes_existentes = {
                medicao.item_contrato_id: medicao
                for medicao in competencia.medicoes.select_related('item_contrato')
            }

        if self.permite_pro_rata:
            self.fields['aplicar_pro_rata'] = forms.BooleanField(
                label='Aplicar pró-rata nesta competência',
                required=False,
                initial=bool(getattr(competencia, 'aplicar_pro_rata', False)),
                help_text='Use esta opção quando a primeira ou a última competência precisar tratamento proporcional.',
            )

        for item in self.itens:
            medicao = medicoes_existentes.get(item.pk)
            self.fields[f'quantidade_{item.pk}'] = forms.DecimalField(
                label=f'Quantidade medida do item {item.ordem}',
                required=False,
                min_value=0,
                decimal_places=2,
                max_digits=14,
                initial=getattr(medicao, 'quantidade', None),
                widget=forms.NumberInput(
                    attrs={
                        'class': BOOTSTRAP_INPUT,
                        'step': '0.01',
                        'min': '0',
                        'placeholder': '0,00',
                    }
                ),
            )

        # A medição expandida concentra também os aceites, dados da nota principal
        # e o bloco financeiro opcional da nota adicional.
        self.fields['aceite_provisorio_arquivo'] = forms.FileField(
            label='Comprovação do aceite provisório',
            required=False,
            widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'application/pdf,.pdf'}),
        )
        self.fields['data_aceite_provisorio'] = forms.DateField(
            label='Data do aceite provisório',
            required=False,
            initial=getattr(competencia, 'data_aceite_provisorio', None),
            input_formats=[HTML5_DATE_FORMAT],
            widget=html5_date_input({'class': BOOTSTRAP_INPUT}),
        )
        self.fields['prazo_aceite_definitivo_dias'] = forms.IntegerField(
            label='Prazo para aceite definitivo (dias corridos)',
            required=False,
            min_value=1,
            initial=getattr(competencia, 'prazo_aceite_definitivo_dias', None),
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'min': '1'}),
        )
        self.fields['aceite_definitivo_arquivo'] = forms.FileField(
            label='Comprovação do aceite definitivo',
            required=False,
            widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'application/pdf,.pdf'}),
        )
        self.fields['data_aceite_definitivo'] = forms.DateField(
            label='Data do aceite definitivo',
            required=False,
            initial=getattr(competencia, 'data_aceite_definitivo', None),
            input_formats=[HTML5_DATE_FORMAT],
            widget=html5_date_input({'class': BOOTSTRAP_INPUT}),
        )
        self.fields['prazo_pagamento_dias'] = forms.IntegerField(
            label='Prazo para pagamento (dias corridos)',
            required=False,
            min_value=1,
            initial=getattr(competencia, 'prazo_pagamento_dias', None),
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'min': '1'}),
        )
        self.fields['nota_fiscal_fatura'] = forms.FileField(
            label='Nota fiscal principal',
            required=False,
            widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'application/pdf,.pdf'}),
        )
        self.fields['numero_nota_fiscal'] = forms.CharField(
            label='Número da nota fiscal',
            required=False,
            initial=getattr(competencia, 'numero_nota_fiscal', ''),
            widget=forms.TextInput(attrs={'class': BOOTSTRAP_INPUT}),
        )
        self.fields['valor_nota_fiscal'] = forms.DecimalField(
            label='Valor da nota fiscal',
            required=False,
            min_value=0,
            decimal_places=2,
            max_digits=14,
            initial=getattr(competencia, 'valor_nota_fiscal', None),
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01', 'min': '0'}),
        )
        valor_nota_inicial = Decimal(getattr(competencia, 'valor_nota_fiscal', Decimal('0.00')) or Decimal('0.00'))
        origem_inicial = None
        if valor_nota_inicial > Decimal('0.00'):
            if valor_nota_inicial == self.valor_medido_referencia:
                origem_inicial = self.ORIGEM_VALOR_NOTA_MEDICAO
            else:
                origem_inicial = self.ORIGEM_VALOR_NOTA_MANUAL
        self.fields['origem_valor_nota_fiscal'] = forms.ChoiceField(
            label='Origem do valor da nota fiscal',
            required=False,
            initial=origem_inicial,
            choices=(
                (self.ORIGEM_VALOR_NOTA_MEDICAO, 'Usar valor da medição'),
                (self.ORIGEM_VALOR_NOTA_MANUAL, 'Preencher manualmente'),
            ),
            widget=forms.RadioSelect,
        )
        if origem_inicial == self.ORIGEM_VALOR_NOTA_MEDICAO and valor_nota_inicial <= Decimal('0.00'):
            self.fields['valor_nota_fiscal'].initial = self.valor_medido_referencia
        if origem_inicial != self.ORIGEM_VALOR_NOTA_MANUAL:
            self.fields['valor_nota_fiscal'].widget.attrs['readonly'] = 'readonly'
        self.fields['valor_nota_fiscal'].widget.attrs['data-origem-medicao'] = '1' if origem_inicial == self.ORIGEM_VALOR_NOTA_MEDICAO else '0'
        for nome, rotulo in (
            ('retencao_ir', 'Retenção IR'),
            ('retencao_inss', 'Retenção INSS'),
            ('retencao_iss', 'Retenção ISS'),
            ('retencao_pis_pasep', 'Retenção PIS/PASEP'),
            ('retencao_cofins', 'Retenção COFINS'),
        ):
            self.fields[nome] = forms.DecimalField(
                label=rotulo,
                required=False,
                min_value=0,
                decimal_places=2,
                max_digits=14,
                initial=getattr(competencia, nome, None),
                widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01', 'min': '0'}),
            )
        self.fields['valor_liberado_final'] = forms.DecimalField(
            label='Valor a ser pago',
            required=False,
            decimal_places=2,
            max_digits=14,
            initial=getattr(competencia, 'valor_liberado_final', None),
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'readonly': 'readonly', 'step': '0.01'}),
        )
        self.fields['nota_adicional_arquivo'] = forms.FileField(
            label='Nota adicional / débito',
            required=False,
            widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'application/pdf,.pdf'}),
        )
        self.fields['nota_adicional_nao_consta'] = forms.BooleanField(
            label='Não consta',
            required=False,
            initial=bool(getattr(competencia, 'nota_adicional_nao_consta', False)),
        )
        self.fields['numero_nota_adicional'] = forms.CharField(
            label='Número da nota adicional',
            required=False,
            initial=getattr(competencia, 'numero_nota_adicional', ''),
            widget=forms.TextInput(attrs={'class': BOOTSTRAP_INPUT}),
        )
        self.fields['valor_nota_adicional'] = forms.DecimalField(
            label='Valor da nota adicional',
            required=False,
            min_value=0,
            decimal_places=2,
            max_digits=14,
            initial=getattr(competencia, 'valor_nota_adicional', None),
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01', 'min': '0'}),
        )
        for nome, rotulo in (
            ('retencao_ir_adicional', 'Retenção IR da nota adicional'),
            ('retencao_inss_adicional', 'Retenção INSS da nota adicional'),
            ('retencao_iss_adicional', 'Retenção ISS da nota adicional'),
            ('retencao_pis_pasep_adicional', 'Retenção PIS/PASEP da nota adicional'),
            ('retencao_cofins_adicional', 'Retenção COFINS da nota adicional'),
        ):
            self.fields[nome] = forms.DecimalField(
                label=rotulo,
                required=False,
                min_value=0,
                decimal_places=2,
                max_digits=14,
                initial=getattr(competencia, nome, None),
                widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01', 'min': '0'}),
            )
        self.fields['valor_liquido_nota_adicional'] = forms.DecimalField(
            label='Valor líquido da nota adicional',
            required=False,
            decimal_places=2,
            max_digits=14,
            initial=getattr(competencia, 'valor_liquido_nota_adicional', None),
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'readonly': 'readonly', 'step': '0.01'}),
        )
        self.fields['observacoes_medicao'] = forms.CharField(
            label='Observações finais',
            required=False,
            initial=getattr(competencia, 'observacoes_medicao', ''),
            widget=forms.Textarea(attrs={'class': BOOTSTRAP_TEXTAREA, 'rows': 3}),
        )
        self.nota_principal_liberada = self._nota_principal_liberada()
        self.nota_adicional_liberada = self._nota_adicional_liberada()
        self.etapas_fluxo = self._montar_etapas_fluxo()
        self._aplicar_bloqueios_campos_preenchidos(medicoes_existentes)
        self._aplicar_bloqueios_fluxo_sequencial()

    def _bloquear_campo(self, nome):
        """Congela um campo já preenchido para preservar o histórico salvo."""

        campo = self.fields.get(nome)
        if campo is None:
            return
        campo.disabled = True
        classe_atual = campo.widget.attrs.get('class', '')
        campo.widget.attrs['class'] = f'{classe_atual} bg-light'.strip()
        campo.widget.attrs['aria-disabled'] = 'true'

    def _aplicar_bloqueios_campos_preenchidos(self, medicoes_existentes):
        """Bloqueia apenas os campos que já têm conteúdo persistido na competência."""

        if self.competencia is None:
            return

        if self.permite_pro_rata and bool(getattr(self.competencia, 'aplicar_pro_rata', False)):
            self._bloquear_campo('aplicar_pro_rata')

        for item in self.itens:
            medicao = medicoes_existentes.get(item.pk)
            if medicao and getattr(medicao, 'quantidade', None) not in (None, Decimal('0.00')):
                self._bloquear_campo(f'quantidade_{item.pk}')

        bloqueios_diretos = {
            'aceite_provisorio_arquivo': bool(self.competencia.aceite_provisorio_arquivo),
            'data_aceite_provisorio': bool(self.competencia.data_aceite_provisorio),
            'prazo_aceite_definitivo_dias': bool(self.competencia.prazo_aceite_definitivo_dias),
            'aceite_definitivo_arquivo': bool(self.competencia.aceite_definitivo_arquivo),
            'data_aceite_definitivo': bool(self.competencia.data_aceite_definitivo),
            'prazo_pagamento_dias': bool(self.competencia.prazo_pagamento_dias),
            'nota_fiscal_fatura': bool(self.competencia.nota_fiscal_fatura),
            'numero_nota_fiscal': bool((self.competencia.numero_nota_fiscal or '').strip()),
            'origem_valor_nota_fiscal': (self.competencia.valor_nota_fiscal or Decimal('0.00')) > Decimal('0.00'),
            'valor_nota_fiscal': (self.competencia.valor_nota_fiscal or Decimal('0.00')) > Decimal('0.00'),
            'nota_adicional_arquivo': bool(self.competencia.nota_adicional_arquivo),
            'nota_adicional_nao_consta': bool(self.competencia.nota_adicional_nao_consta),
            'numero_nota_adicional': bool((self.competencia.numero_nota_adicional or '').strip()),
            'valor_nota_adicional': (self.competencia.valor_nota_adicional or Decimal('0.00')) > Decimal('0.00'),
            'observacoes_medicao': bool((self.competencia.observacoes_medicao or '').strip()),
        }
        for nome, bloquear in bloqueios_diretos.items():
            if bloquear:
                self._bloquear_campo(nome)

        if self.competencia.nota_adicional_nao_consta:
            for nome in (
                'nota_adicional_arquivo',
                'numero_nota_adicional',
                'valor_nota_adicional',
                'retencao_ir_adicional',
                'retencao_inss_adicional',
                'retencao_iss_adicional',
                'retencao_pis_pasep_adicional',
                'retencao_cofins_adicional',
                'valor_liquido_nota_adicional',
            ):
                self._bloquear_campo(nome)

        for nome in (
            'retencao_ir',
            'retencao_inss',
            'retencao_iss',
            'retencao_pis_pasep',
            'retencao_cofins',
            'retencao_ir_adicional',
            'retencao_inss_adicional',
            'retencao_iss_adicional',
            'retencao_pis_pasep_adicional',
            'retencao_cofins_adicional',
        ):
            if (getattr(self.competencia, nome, Decimal('0.00')) or Decimal('0.00')) > Decimal('0.00'):
                self._bloquear_campo(nome)

    def _nota_principal_liberada(self):
        """A segunda etapa só abre após existir conteúdo salvo na medição."""

        return bool(self.competencia and self.competencia.medicao_tem_conteudo)

    def _nota_adicional_liberada(self):
        """A terceira etapa depende do salvamento prévio da medição e da nota principal."""

        return bool(self.competencia and self.competencia.medicao_tem_conteudo and self.competencia.nota_principal_tem_conteudo)

    def _montar_etapas_fluxo(self):
        """Entrega um resumo simples para o template mostrar a ordem operacional da tela."""

        return [
            {
                'titulo': '1. Medição',
                # A primeira etapa permanece visualmente disponível durante todo o fluxo.
                'descricao': '',
                'status_classe': 'available',
                'status_rotulo': 'Liberada',
            },
            {
                'titulo': '2. Nota Fiscal Principal',
                # Mantém uma orientação curta e estável tanto no estado bloqueado quanto liberado.
                'descricao': 'Só libera após salvar a medição.',
                'status_classe': 'available' if self.nota_principal_liberada else 'blocked',
                'status_rotulo': 'Liberada' if self.nota_principal_liberada else 'Bloqueada',
            },
            {
                'titulo': '3. Nota Fiscal Adicional',
                # Mantém uma orientação curta e estável tanto no estado bloqueado quanto liberado.
                'descricao': 'Só libera após salvar a medição e a nota principal.',
                'status_classe': 'available' if self.nota_adicional_liberada else 'blocked',
                'status_rotulo': 'Liberada' if self.nota_adicional_liberada else 'Bloqueada',
            },
            {
                'titulo': 'Observações finais',
                'descricao': 'Fica sempre disponível.',
                'status_classe': 'available',
                'status_rotulo': 'Concluída',
            },
        ]

    def _aplicar_bloqueios_fluxo_sequencial(self):
        """Protege as etapas posteriores quando a competência ainda não alcançou o ponto de liberação."""

        if not self.nota_principal_liberada:
            for nome in self.CAMPOS_NOTA_PRINCIPAL:
                self._bloquear_campo(nome)
        if not self.nota_adicional_liberada:
            for nome in self.CAMPOS_NOTA_ADICIONAL:
                self._bloquear_campo(nome)

    def _dados_brutos_da_secao_informados(self, nomes_campos):
        """Detecta tentativa de envio manual de campos bloqueados, mesmo fora do HTML padrão."""

        for nome in nomes_campos:
            arquivo = self.files.get(nome)
            if arquivo:
                return True
            valor = self.data.get(nome)
            if valor is None:
                continue
            if isinstance(valor, str):
                if valor.strip():
                    return True
                continue
            if valor:
                return True
        return False

    def _permite_pro_rata(self):
        """Libera o pró-rata apenas nas bordas da vigência inicial do contrato."""

        if self.contrato is None or self.competencia is None:
            return False
        ultimo_dia_vigencia = inclusive_end_date(self.contrato.data_inicio_vigencia, self.contrato.prazo_inicial_meses)
        return (
            self.competencia.periodo_inicio == self.contrato.data_inicio_vigencia
            or self.competencia.periodo_fim == ultimo_dia_vigencia
        )

    def clean(self):
        cleaned = super().clean()
        if not self.nota_principal_liberada and self._dados_brutos_da_secao_informados(self.CAMPOS_NOTA_PRINCIPAL):
            self.add_error(None, 'Salve a etapa de medição antes de preencher a nota fiscal principal.')
        if not self.nota_adicional_liberada and self._dados_brutos_da_secao_informados(self.CAMPOS_NOTA_ADICIONAL):
            self.add_error(None, 'Salve a medição e a nota fiscal principal antes de preencher a nota fiscal adicional.')

        for nome in ('aceite_provisorio_arquivo', 'aceite_definitivo_arquivo', 'nota_fiscal_fatura', 'nota_adicional_arquivo'):
            arquivo = cleaned.get(nome)
            if arquivo and not getattr(arquivo, '_committed', False):
                cleaned[nome] = validar_upload_pdf(arquivo)

        valor_nota = Decimal(cleaned.get('valor_nota_fiscal') or Decimal('0.00'))
        origem_valor_nota = cleaned.get('origem_valor_nota_fiscal') or ''
        if origem_valor_nota == self.ORIGEM_VALOR_NOTA_MEDICAO:
            valor_nota = self.valor_medido_referencia
            cleaned['valor_nota_fiscal'] = valor_nota
        total_retencoes = sum(
            (
                Decimal(cleaned.get('retencao_ir') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_inss') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_iss') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_pis_pasep') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_cofins') or Decimal('0.00')),
            ),
            Decimal('0.00'),
        )
        if total_retencoes > valor_nota:
            self.add_error('retencao_cofins', 'A soma das retenções não pode superar o valor da nota fiscal.')
        cleaned['valor_liberado_final'] = valor_nota - total_retencoes

        nota_adicional_informada = any(
            [
                cleaned.get('nota_adicional_arquivo'),
                (cleaned.get('numero_nota_adicional') or '').strip(),
                cleaned.get('valor_nota_adicional'),
            ]
        )
        nota_adicional_nao_consta = bool(cleaned.get('nota_adicional_nao_consta'))
        valor_nota_adicional = Decimal(cleaned.get('valor_nota_adicional') or Decimal('0.00'))
        total_retencoes_adicionais = sum(
            (
                Decimal(cleaned.get('retencao_ir_adicional') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_inss_adicional') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_iss_adicional') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_pis_pasep_adicional') or Decimal('0.00')),
                Decimal(cleaned.get('retencao_cofins_adicional') or Decimal('0.00')),
            ),
            Decimal('0.00'),
        )
        if total_retencoes_adicionais > valor_nota_adicional:
            self.add_error('retencao_cofins_adicional', 'A soma das retenções não pode superar o valor da nota adicional.')
        cleaned['valor_liquido_nota_adicional'] = valor_nota_adicional - total_retencoes_adicionais
        if nota_adicional_nao_consta and nota_adicional_informada:
            self.add_error('nota_adicional_nao_consta', 'Desmarque "Não consta" para informar uma nota adicional.')
        if nota_adicional_informada:
            if not cleaned.get('nota_adicional_arquivo'):
                self.add_error('nota_adicional_arquivo', 'Anexe a nota adicional.')
            if not (cleaned.get('numero_nota_adicional') or '').strip():
                self.add_error('numero_nota_adicional', 'Informe o número da nota adicional.')
            if not cleaned.get('valor_nota_adicional'):
                self.add_error('valor_nota_adicional', 'Informe o valor da nota adicional.')
        return cleaned


class AvaliacaoCompetenciaV2Form(forms.Form):
    """Formulário dinâmico para preencher avaliação do fiscal e do gestor por item."""

    avaliacao_assinada = forms.FileField(
        label='Avaliação de Qualidade assinada pelas partes',
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'application/pdf,.pdf'}),
    )
    observacoes = forms.CharField(
        label='Observações gerais',
        required=False,
        widget=forms.Textarea(attrs={'class': BOOTSTRAP_TEXTAREA, 'rows': 3}),
    )

    def _calcular_resultado_automatico(self, competencia):
        """Replica o fechamento automático para exibir nota, faixa e valor coerentes no formulário."""

        acumulado = Decimal('0.00')
        for resposta in self.respostas:
            acumulado += (resposta.nota_valor or Decimal('0.00')) * (
                (resposta.item_peso_percentual or Decimal('0.00')) / Decimal('100.00')
            )
        nota_final = Decimal(f'{acumulado:.2f}')
        percentual = Decimal('100.00')
        for faixa in getattr(self.avaliacao, 'faixas_liberacao_snapshot', []) or []:
            nota_minima = Decimal(faixa['nota_minima'])
            nota_maxima = Decimal(faixa['nota_maxima']) if faixa.get('nota_maxima') not in {'', None} else None
            if nota_final < nota_minima:
                continue
            if nota_maxima is not None and nota_final > nota_maxima:
                continue
            percentual = Decimal(faixa['percentual_liberacao'])
            break
        valor_final = Decimal('0.00')
        if competencia is not None:
            valor_final = (getattr(competencia, 'valor_nota_fiscal', Decimal('0.00')) or Decimal('0.00')) * (
                percentual / Decimal('100.00')
            )
        return {
            'nota_final': nota_final,
            'percentual': Decimal(f'{percentual:.2f}'),
            'valor_final': Decimal(f'{valor_final:.2f}'),
        }

    def _fechamento_avaliacao_liberado(self, competencia):
        """Só libera o fechamento quando notas, justificativas e PDF assinado já estiverem completos."""

        if competencia is None:
            return False
        if not getattr(competencia.avaliacao_assinada, 'name', ''):
            return False

        for resposta in self.respostas:
            if resposta.nota_fiscal_valor is None or resposta.nota_gestor_valor is None:
                return False
            if resposta.nota_fiscal_valor < self.max_nota and not (resposta.justificativa_fiscal or '').strip():
                return False
            if resposta.nota_gestor_valor < self.max_nota and not (resposta.manifestacao_gestor_item or '').strip():
                return False
        return bool(self.respostas)

    def __init__(self, *args, avaliacao=None, **kwargs):
        self.pode_preencher_fiscal = kwargs.pop('pode_preencher_fiscal', False)
        self.pode_preencher_gestor = kwargs.pop('pode_preencher_gestor', False)
        super().__init__(*args, **kwargs)
        self.avaliacao = avaliacao
        # Guarda quais papéis realmente foram acionados no submit, evitando que o valor inicial "zerado"
        # seja tratado como preenchimento efetivo do outro papel.
        self.papeis_informados = {}
        self.respostas = list(avaliacao.itens.order_by('grupo_ordem', 'item_ordem', 'id') if avaliacao is not None else [])
        escala = avaliacao.formulario_snapshot.get('escala', []) if avaliacao is not None else []
        self.max_nota = max((Decimal(item['valor']) for item in escala), default=Decimal('0.00'))
        self.min_nota = min((Decimal(item['valor']) for item in escala), default=Decimal('0.00'))
        self.max_nota_js = format(self.max_nota, 'f')
        choices = [('', 'Selecione')] + [(item['valor'], f"{item['valor']} - {item['legenda']}") for item in escala]
        queryset = User.objects.filter(is_active=True).select_related('perfil').order_by('perfil__nome_completo', 'username')
        percentual_inicial = getattr(avaliacao, 'percentual_liberacao_sugerido', Decimal('100.00')) if avaliacao is not None else Decimal('100.00')
        nota_final_inicial = getattr(avaliacao, 'nota_final', Decimal('0.00')) if avaliacao is not None else Decimal('0.00')
        competencia = getattr(avaliacao, 'competencia', None)
        valor_final_inicial = (
            getattr(competencia, 'valor_liberado_final', Decimal('0.00'))
            if competencia is not None
            else Decimal('0.00')
        )

        if avaliacao is not None:
            self.fields['observacoes'].initial = avaliacao.observacoes

        competencia_possui_pdf_assinado = bool(
            competencia is not None and getattr(competencia.avaliacao_assinada, 'name', '')
        )
        self.fechamento_avaliacao_liberado = self._fechamento_avaliacao_liberado(competencia)
        self.fechamento_avaliacao_concluido = bool(getattr(avaliacao, 'concluida_em', None))
        resultado_automatico = self._calcular_resultado_automatico(competencia)
        nota_final_exibida = (
            resultado_automatico['nota_final']
            if competencia_possui_pdf_assinado
            else nota_final_inicial
        )

        self.fields['nota_final_aprovada'] = forms.DecimalField(
            label='Nota Final',
            required=False,
            min_value=self.min_nota,
            max_value=self.max_nota if self.max_nota > self.min_nota else None,
            decimal_places=2,
            max_digits=8,
            initial=nota_final_exibida,
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01', 'min': '0'}),
        )
        if competencia_possui_pdf_assinado:
            # Depois do retorno do PDF assinado, a nota final passa a refletir só o cálculo automático.
            self.fields['nota_final_aprovada'].widget.attrs['readonly'] = 'readonly'
            self.fields['nota_final_aprovada'].widget.attrs['class'] = (
                f"{self.fields['nota_final_aprovada'].widget.attrs.get('class', '')} bg-light"
            ).strip()
        self.fields['percentual_liberacao_aprovado'] = forms.DecimalField(
            label='Faixa de Liberação (%)',
            required=False,
            min_value=0,
            max_value=100,
            decimal_places=2,
            max_digits=8,
            initial=resultado_automatico['percentual'],
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01', 'min': '0', 'max': '100'}),
        )
        self.fields['percentual_liberacao_aprovado'].widget.attrs['readonly'] = 'readonly'
        self.fields['percentual_liberacao_aprovado'].widget.attrs['class'] = (
            f"{self.fields['percentual_liberacao_aprovado'].widget.attrs.get('class', '')} bg-light"
        ).strip()
        self.fields['percentual_liberacao_aprovado'].disabled = True
        self.fields['valor_liberado_final'] = forms.DecimalField(
            label='Valor a Pagar',
            required=False,
            min_value=0,
            decimal_places=2,
            max_digits=14,
            initial=valor_final_inicial,
            widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01', 'min': '0'}),
        )
        if not self.fechamento_avaliacao_liberado or self.fechamento_avaliacao_concluido:
            for nome_campo in (
                'nota_final_aprovada',
                'percentual_liberacao_aprovado',
                'valor_liberado_final',
            ):
                self.fields[nome_campo].disabled = True

        self.campos_assinatura = (
            ('gestor_pagamento', 'gestor_pagamento_nome_manual', 'gestor_pagamento_em_exercicio', 'Gestor do contrato'),
            ('coordenadora_pagamento', 'coordenadora_pagamento_nome_manual', 'coordenadora_em_exercicio', 'Coordenadora'),
            ('diretora_pagamento', 'diretora_pagamento_nome_manual', 'diretora_em_exercicio', 'Diretora'),
            ('subsecretario_pagamento', 'subsecretario_pagamento_nome_manual', 'subsecretario_em_exercicio', 'Subsecretário'),
        )
        for nome_campo, campo_manual, campo_exercicio, rotulo in self.campos_assinatura:
            nome_modelo_manual = campo_manual
            nome_modelo_exercicio = campo_exercicio
            label_manual = f'Nome manual de {rotulo.lower()}'
            initial_manual = getattr(competencia, nome_modelo_manual, '') if competencia is not None else ''
            initial_exercicio = bool(getattr(competencia, nome_modelo_exercicio, False)) if competencia is not None else False
            initial_usuario = getattr(competencia, nome_campo, None) if competencia is not None else None

            self.fields[nome_campo] = UsuarioPerfilChoiceField(
                queryset=queryset,
                required=False,
                label=rotulo,
            )
            self.fields[nome_campo].widget.attrs['class'] = 'form-select form-select-lg'
            self.fields[campo_manual] = forms.CharField(
                label=label_manual,
                required=False,
                initial=initial_manual,
                widget=forms.TextInput(
                    attrs={
                        'class': BOOTSTRAP_INPUT,
                        'placeholder': 'Preencha manualmente se o nome não estiver na lista.',
                    }
                ),
            )
            self.fields[campo_exercicio] = forms.BooleanField(
                label='Em exercício',
                required=False,
                initial=initial_exercicio,
            )
            self.fields[nome_campo].initial = initial_usuario
        if competencia is not None and not self.fields['gestor_pagamento'].initial and competencia.contrato.gestor_contrato_id:
            self.fields['gestor_pagamento'].initial = competencia.contrato.gestor_contrato
        if not self.fechamento_avaliacao_liberado or self.fechamento_avaliacao_concluido:
            for nome_campo, campo_manual, campo_exercicio, _rotulo in self.campos_assinatura:
                self.fields[nome_campo].disabled = True
                self.fields[campo_manual].disabled = True
                self.fields[campo_exercicio].disabled = True

        for resposta in self.respostas:
            self.fields[f'nota_fiscal_{resposta.pk}'] = forms.TypedChoiceField(
                label='Nota do fiscal',
                required=False,
                choices=choices,
                coerce=Decimal,
                # A avaliação deve nascer em branco para explicitar quando o item ainda não foi analisado.
                initial=resposta.nota_fiscal_valor,
                widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
            )
            self.fields[f'justificativa_fiscal_{resposta.pk}'] = forms.CharField(
                label='Justificativa do fiscal',
                required=False,
                initial=resposta.justificativa_fiscal,
                widget=forms.Textarea(attrs={'class': BOOTSTRAP_TEXTAREA, 'rows': 2}),
            )
            self.fields[f'nota_gestor_{resposta.pk}'] = forms.TypedChoiceField(
                label='Nota do gestor',
                required=False,
                choices=choices,
                coerce=Decimal,
                # O gestor também começa sem valor para não sugerir nota antes da manifestação real.
                initial=resposta.nota_gestor_valor,
                widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
            )
            self.fields[f'manifestacao_gestor_item_{resposta.pk}'] = forms.CharField(
                label='Manifestação do gestor',
                required=False,
                initial=resposta.manifestacao_gestor_item,
                widget=forms.Textarea(attrs={'class': BOOTSTRAP_TEXTAREA, 'rows': 2}),
            )

            if not self.pode_preencher_fiscal:
                self.fields[f'nota_fiscal_{resposta.pk}'].disabled = True
                self.fields[f'justificativa_fiscal_{resposta.pk}'].disabled = True
            if not self.pode_preencher_gestor:
                self.fields[f'nota_gestor_{resposta.pk}'].disabled = True
                self.fields[f'manifestacao_gestor_item_{resposta.pk}'].disabled = True

    def _papel_foi_informado(self, resposta, papel, cleaned):
        """Distingue um envio intencional do papel de um simples valor inicial vindo do select."""

        if papel == 'fiscal':
            campo_nota = f'nota_fiscal_{resposta.pk}'
            campo_texto = f'justificativa_fiscal_{resposta.pk}'
        else:
            campo_nota = f'nota_gestor_{resposta.pk}'
            campo_texto = f'manifestacao_gestor_item_{resposta.pk}'

        texto = (cleaned.get(campo_texto) or '').strip()
        return bool(
            (campo_nota in self.data and campo_nota in self.changed_data)
            or (campo_texto in self.data and campo_texto in self.changed_data)
            or texto
        )

    def clean(self):
        cleaned = super().clean()
        arquivo_assinado = cleaned.get('avaliacao_assinada')
        if arquivo_assinado:
            cleaned['avaliacao_assinada'] = validar_upload_pdf(arquivo_assinado)

        def normalizar_nota(valor):
            """Garante comparação numérica mesmo quando o dado ainda vier como texto."""

            if valor in (None, ''):
                return None
            if isinstance(valor, Decimal):
                return valor
            try:
                return Decimal(str(valor))
            except Exception:
                return None

        for resposta in self.respostas:
            nota_fiscal = normalizar_nota(cleaned.get(f'nota_fiscal_{resposta.pk}'))
            justificativa_fiscal = (cleaned.get(f'justificativa_fiscal_{resposta.pk}') or '').strip()
            nota_gestor = normalizar_nota(cleaned.get(f'nota_gestor_{resposta.pk}'))
            manifestacao_gestor = (cleaned.get(f'manifestacao_gestor_item_{resposta.pk}') or '').strip()
            fiscal_informado = self._papel_foi_informado(resposta, 'fiscal', cleaned)
            gestor_informado = self._papel_foi_informado(resposta, 'gestor', cleaned)
            self.papeis_informados[resposta.pk] = {
                'fiscal': fiscal_informado,
                'gestor': gestor_informado,
            }

            if self.pode_preencher_fiscal and fiscal_informado and nota_fiscal is not None and nota_fiscal < self.max_nota and not justificativa_fiscal:
                self.add_error(
                    f'justificativa_fiscal_{resposta.pk}',
                    'Informe a justificativa do fiscal para notas abaixo da máxima.',
                )
            if self.pode_preencher_gestor and gestor_informado and nota_gestor is not None and nota_gestor < self.max_nota and not manifestacao_gestor:
                self.add_error(
                    f'manifestacao_gestor_item_{resposta.pk}',
                    'Informe a manifestação do gestor para notas abaixo da máxima.',
                )

        nota_final_aprovada = normalizar_nota(cleaned.get('nota_final_aprovada'))
        percentual_aprovado = normalizar_nota(cleaned.get('percentual_liberacao_aprovado'))
        valor_liberado_final = normalizar_nota(cleaned.get('valor_liberado_final'))
        cleaned['nota_final_aprovada'] = nota_final_aprovada
        cleaned['percentual_liberacao_aprovado'] = percentual_aprovado
        cleaned['valor_liberado_final'] = valor_liberado_final

        for nome_campo, campo_manual, campo_exercicio, _rotulo in self.campos_assinatura:
            cleaned[campo_manual] = (cleaned.get(campo_manual) or '').strip()
            if cleaned.get(campo_exercicio) and not (cleaned.get(nome_campo) or cleaned[campo_manual]):
                self.add_error(campo_manual, 'Selecione um usuário ou informe o nome manual para marcar "Em exercício".')
        return cleaned


class CompetenciaPagamentoExecucaoV2Form(BootstrapModelForm):
    """Recebe documentos finais e o valor aprovado no pagamento da competência."""

    class Meta:
        model = CompetenciaPagamento
        # O campo 'atestado_realizacao' foi retirado pois o documento passa a ser gerado automaticamente
        fields = [
            'nota_fiscal_fatura',
            'valor_nota_fiscal',
            'retencao_ir',
            'retencao_inss',
            'retencao_iss',
            'retencao_pis_pasep',
            'retencao_cofins',
            'valor_liberado_final',
            'gestor_pagamento',
            'gestor_pagamento_em_exercicio',
            'coordenadora_pagamento',
            'coordenadora_em_exercicio',
            'diretora_pagamento',
            'diretora_em_exercicio',
            'subsecretario_pagamento',
            'subsecretario_em_exercicio',
            'data_pagamento',
            'justificativa_divergencia',
        ]
        widgets = {
            'valor_liberado_final': forms.NumberInput(attrs={'readonly': 'readonly'}),
            'data_pagamento': html5_date_input(),
            'justificativa_divergencia': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, competencia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.competencia = competencia
        queryset = User.objects.filter(is_active=True).select_related('perfil').order_by('perfil__nome_completo', 'username')
        for name in (
            'gestor_pagamento',
            'coordenadora_pagamento',
            'diretora_pagamento',
            'subsecretario_pagamento',
        ):
            self.fields[name] = UsuarioPerfilChoiceField(
                queryset=queryset,
                required=False,
                label=self.fields[name].label,
            )
            self.fields[name].widget.attrs['class'] = 'form-select form-select-lg'
        # Restringe o upload de Nota Fiscal apenas a arquivos PDF
        for field_name in ('nota_fiscal_fatura',):
            self.fields[field_name].widget.attrs['accept'] = 'application/pdf,.pdf'
        self.fields['valor_nota_fiscal'].label = 'Valor da nota fiscal'
        self.fields['valor_liberado_final'].label = 'Valor a ser pago'
        self.fields['valor_liberado_final'].help_text = 'Calculado automaticamente: valor da nota fiscal menos retenções.'
        self.fields['valor_liberado_final'].widget.attrs['tabindex'] = '-1'
        self.fields['gestor_pagamento'].help_text = 'Se já houver gestor no contrato, o campo será sugerido automaticamente.'
        if competencia is not None:
            valor_nota_inicial = competencia.valor_nota_fiscal or competencia.valor_liberado_sugerido
            valor_liquido_inicial = valor_nota_inicial - competencia.total_retencoes
            self.fields['valor_nota_fiscal'].initial = valor_nota_inicial
            self.fields['valor_liberado_final'].initial = valor_liquido_inicial
            self.fields['data_pagamento'].initial = timezone.localdate()
            if not self.instance.gestor_pagamento_id and competencia.contrato.gestor_contrato_id:
                self.fields['gestor_pagamento'].initial = competencia.contrato.gestor_contrato

    def clean_nota_fiscal_fatura(self):
        return validar_upload_pdf(self.cleaned_data.get('nota_fiscal_fatura'))

    def clean(self):
        cleaned = super().clean()
        if self.competencia is None:
            return cleaned
        valor_nota = Decimal(cleaned.get('valor_nota_fiscal') or Decimal('0.00'))
        retencoes = [
            Decimal(cleaned.get('retencao_ir') or Decimal('0.00')),
            Decimal(cleaned.get('retencao_inss') or Decimal('0.00')),
            Decimal(cleaned.get('retencao_iss') or Decimal('0.00')),
            Decimal(cleaned.get('retencao_pis_pasep') or Decimal('0.00')),
            Decimal(cleaned.get('retencao_cofins') or Decimal('0.00')),
        ]
        total_retencoes = sum(retencoes, Decimal('0.00'))
        if total_retencoes > valor_nota:
            self.add_error('retencao_cofins', 'A soma das retenções não pode superar o valor da nota fiscal.')
        valor_final = valor_nota - total_retencoes
        cleaned['valor_liberado_final'] = valor_final
        self.instance.valor_liberado_final = valor_final

        return cleaned


class CompetenciaChecklistExtraItemForm(forms.Form):
    """Permite cadastrar itens documentais exclusivos da nota adicional na competência."""

    titulo = forms.CharField(label='Nome do documento', widget=forms.TextInput(attrs={'class': BOOTSTRAP_INPUT}))


class CompetenciaOBExecucaoForm(BootstrapModelForm):
    """Registra a etapa final da competência com a ordem bancária e a data do pagamento."""

    class Meta:
        model = CompetenciaPagamento
        fields = ['ordem_bancaria_arquivo', 'data_pagamento']
        widgets = {
            'data_pagamento': html5_date_input(),
        }

    def clean_ordem_bancaria_arquivo(self):
        return validar_upload_pdf(self.cleaned_data.get('ordem_bancaria_arquivo'))


class EmpresaContratadaForm(BootstrapModelForm):
    class Meta:
        model = EmpresaContratada
        fields = [
            'razao_social',
            'nome_fantasia',
            'cnpj',
            'logradouro',
            'numero',
            'complemento',
            'bairro',
            'cidade',
            'estado',
        ]


class ResponsavelEmpresaForm(BootstrapModelForm):
    class Meta:
        model = ResponsavelEmpresa
        fields = ['nome', 'cpf', 'cargo', 'telefone', 'email', 'ativo']


class PrazoMonitoramentoForm(BootstrapModelForm):
    """Formulário para prazos que serão monitorados no contrato."""

    class Meta:
        model = PrazoMonitoramento
        fields = ['nome', 'data_inicio', 'data_limite', 'anexo']
        widgets = {
            'data_inicio': html5_date_input(),
            'data_limite': html5_date_input(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['data_inicio'].required = False
        self.fields['data_inicio'].help_text = (
            'Opcional. Informe quando o monitoramento deve começar '
            '(reajuste, validade, acordo coletivo etc.). '
            'Se ficar em branco, o sistema usa a data do cadastro.'
        )

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get('data_inicio')
        data_limite = cleaned.get('data_limite')
        if data_inicio and data_limite and data_inicio > data_limite:
            self.add_error('data_inicio', 'A data de início deve ser anterior ou igual à data limite.')
        return cleaned
