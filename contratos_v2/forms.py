# Criado por José Eduardo Santana Martins e OpenAI Codex em 08/06/2026
# Objetivo: Definir formulários do Contratos V2 incluindo checklist, avaliação, medição e pagamento.

import re
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from contratos.forms import validar_upload_pdf
from contratos.services import inclusive_end_date

from .models import (
    AvaliacaoQualidadeCompetenciaV2,
    ChecklistModeloItemV2,
    ChecklistModeloV2,
    CompetenciaPagamentoV2,
    ContratoItemV2,
    ContratoV2,
    EscalaNotaAvaliacaoV2,
    FaixaLiberacaoAvaliacaoV2,
    FormularioAvaliacaoV2,
    GrupoAvaliacaoV2,
    ItemAvaliacaoV2,
    MedicaoItemCompetenciaV2,
)


User = get_user_model()
BOOTSTRAP_INPUT = 'form-control form-control-lg'
BOOTSTRAP_TEXTAREA = 'form-control spi-textarea-compact'
NUMERO_CONTRATO_RE = re.compile(r'^\d{3}/\d{4}$')


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
    for numero in ContratoV2.objects.filter(numero_contrato__endswith=suffix).values_list('numero_contrato', flat=True):
        parsed = parse_numero_contrato(numero)
        if parsed and parsed[1] == ano:
            maior = max(maior, parsed[0])
    return f'{maior + 1:03d}/{ano}'


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


class ContratoV2Form(BootstrapModelForm):
    numero_contrato_incremental = forms.BooleanField(
        label='Preencher número automaticamente',
        required=False,
        initial=True,
        help_text='Gera o próximo número disponível no formato NNN/AAAA conforme o ano da vigência.',
    )

    class Meta:
        model = ContratoV2
        fields = [
            'numero_contrato',
            'apelido',
            'objeto',
            'data_inicio_vigencia',
            'prazo_inicial_meses',
            'vigencia_maxima_meses',
            'empresa_contratada',
            'fiscal_administrativo',
            'fiscal_tecnico',
            'gestor_contrato',
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
        for name in ('fiscal_administrativo', 'fiscal_tecnico', 'gestor_contrato'):
            self.fields[name] = user_field.__class__(queryset=queryset, label=self.fields[name].label)
            self.fields[name].widget.attrs['class'] = 'form-select form-select-lg'

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

        return cleaned


class ContratoItemV2Form(BootstrapModelForm):
    """Formulário enxuto para itens financeiros que alimentam os totais do contrato."""

    class Meta:
        model = ContratoItemV2
        fields = ['ordem', 'descricao', 'codigo_siafisico', 'codigo_catmat_catser', 'quantidade', 'valor_unitario']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ordem'].required = False
        self.fields['ordem'].help_text = 'Se deixar em branco, o sistema usará o próximo número disponível.'


class ChecklistModeloV2Form(BootstrapModelForm):
    class Meta:
        model = ChecklistModeloV2
        fields = ['nome', 'descricao', 'observacoes', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class ChecklistModeloItemV2Form(BootstrapModelForm):
    class Meta:
        model = ChecklistModeloItemV2
        fields = ['ordem', 'titulo', 'descricao', 'obrigatorio']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ordem'].required = False
        self.fields['ordem'].help_text = 'Se deixar em branco, o sistema usará a próxima ordem disponível.'


class FormularioAvaliacaoV2Form(BootstrapModelForm):
    class Meta:
        model = FormularioAvaliacaoV2
        fields = ['nome', 'descricao', 'ativo', 'observacoes']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class EscalaNotaAvaliacaoV2Form(BootstrapModelForm):
    class Meta:
        model = EscalaNotaAvaliacaoV2
        fields = ['valor', 'legenda']


class FaixaLiberacaoAvaliacaoV2Form(BootstrapModelForm):
    class Meta:
        model = FaixaLiberacaoAvaliacaoV2
        fields = ['nota_minima', 'nota_maxima', 'percentual_liberacao']


class GrupoAvaliacaoV2Form(BootstrapModelForm):
    class Meta:
        model = GrupoAvaliacaoV2
        fields = ['nome', 'descricao']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


class ItemAvaliacaoV2Form(BootstrapModelForm):
    """Mantém o cadastro do item focado no conteúdo, com ordem controlada pelo sistema."""

    class Meta:
        model = ItemAvaliacaoV2
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

    def __init__(self, *args, contrato=None, competencia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contrato = contrato
        self.competencia = competencia
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

    def _permite_pro_rata(self):
        """Libera o pró-rata apenas nas bordas da vigência inicial do contrato."""

        if self.contrato is None or self.competencia is None:
            return False
        ultimo_dia_vigencia = inclusive_end_date(self.contrato.data_inicio_vigencia, self.contrato.prazo_inicial_meses)
        return (
            self.competencia.periodo_inicio == self.contrato.data_inicio_vigencia
            or self.competencia.periodo_fim == ultimo_dia_vigencia
        )


class AvaliacaoCompetenciaV2Form(forms.Form):
    """Formulário dinâmico para preencher notas, justificativas e manifestação do gestor."""

    observacoes = forms.CharField(
        label='Observações gerais',
        required=False,
        widget=forms.Textarea(attrs={'class': BOOTSTRAP_TEXTAREA, 'rows': 3}),
    )

    def __init__(self, *args, avaliacao=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.avaliacao = avaliacao
        self.respostas = list(avaliacao.itens.order_by('grupo_ordem', 'item_ordem', 'id') if avaliacao is not None else [])
        escala = avaliacao.formulario_snapshot.get('escala', []) if avaliacao is not None else []
        self.max_nota = max((Decimal(item['valor']) for item in escala), default=Decimal('0.00'))
        self.max_nota_js = format(self.max_nota, 'f')
        choices = [('', 'Selecione')] + [(item['valor'], f"{item['valor']} - {item['legenda']}") for item in escala]

        if avaliacao is not None:
            self.fields['observacoes'].initial = avaliacao.observacoes

        for resposta in self.respostas:
            self.fields[f'nota_{resposta.pk}'] = forms.TypedChoiceField(
                label=f'Nota do item {resposta.item_ordem}',
                required=True,
                choices=choices,
                coerce=Decimal,
                initial=resposta.nota_valor,
                widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
            )
            self.fields[f'justificativa_{resposta.pk}'] = forms.CharField(
                label='Justificativa do fiscal',
                required=False,
                initial=resposta.justificativa_fiscal,
                widget=forms.Textarea(attrs={'class': BOOTSTRAP_TEXTAREA, 'rows': 2}),
            )
            self.fields[f'manifestacao_gestor_item_{resposta.pk}'] = forms.CharField(
                label='Manifestação do gestor',
                required=False,
                initial=resposta.manifestacao_gestor_item,
                widget=forms.Textarea(attrs={'class': BOOTSTRAP_TEXTAREA, 'rows': 2}),
            )

    def clean(self):
        cleaned = super().clean()
        for resposta in self.respostas:
            nota = cleaned.get(f'nota_{resposta.pk}')
            justificativa = (cleaned.get(f'justificativa_{resposta.pk}') or '').strip()
            if nota is None:
                continue
            if nota < self.max_nota:
                if not justificativa:
                    self.add_error(f'justificativa_{resposta.pk}', 'Informe a justificativa do fiscal para notas abaixo da máxima.')
        return cleaned


class CompetenciaPagamentoExecucaoV2Form(BootstrapModelForm):
    """Recebe documentos finais e o valor aprovado no pagamento da competência."""

    class Meta:
        model = CompetenciaPagamentoV2
        fields = [
            'nota_fiscal_fatura',
            'atestado_realizacao',
            'despacho_dof',
            'valor_liberado_final',
            'data_pagamento',
            'justificativa_divergencia',
        ]
        widgets = {
            'data_pagamento': forms.DateInput(attrs={'type': 'date'}),
            'justificativa_divergencia': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, competencia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.competencia = competencia
        for field_name in ('nota_fiscal_fatura', 'atestado_realizacao', 'despacho_dof'):
            self.fields[field_name].widget.attrs['accept'] = 'application/pdf,.pdf'
        if competencia is not None:
            self.fields['valor_liberado_final'].initial = competencia.valor_liberado_sugerido
            self.fields['data_pagamento'].initial = timezone.localdate()

    def clean_nota_fiscal_fatura(self):
        return validar_upload_pdf(self.cleaned_data.get('nota_fiscal_fatura'))

    def clean_atestado_realizacao(self):
        return validar_upload_pdf(self.cleaned_data.get('atestado_realizacao'))

    def clean_despacho_dof(self):
        return validar_upload_pdf(self.cleaned_data.get('despacho_dof'))

    def clean(self):
        cleaned = super().clean()
        if self.competencia is None:
            return cleaned
        valor_final = cleaned.get('valor_liberado_final')
        if valor_final is not None and Decimal(valor_final) != Decimal(self.competencia.valor_liberado_sugerido or Decimal('0.00')):
            if not (cleaned.get('justificativa_divergencia') or '').strip():
                self.add_error('justificativa_divergencia', 'Explique a divergência entre o valor sugerido e o valor final.')
        return cleaned
