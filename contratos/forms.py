# Criado por José Eduardo Santana Martins e OpenAI Codex em 06/06/2026
# Objetivo: Definir formulários Bootstrap do módulo de contratos.

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone

from usuarios.models import UsuarioPerfil

from .models import (
    AvaliacaoCriterioCompetencia,
    AvaliacaoQualidadeCompetencia,
    ChecklistPagamentoAnexo,
    ChecklistPagamentoItem,
    ChecklistPagamentoModelo,
    CompetenciaPagamento,
    Contrato,
    ContratoDetalhamentoItem,
    ContratoItem,
    CriterioAvaliacaoQualidade,
    DocumentoContrato,
    EmpresaContratada,
    EventoFinanceiroContrato,
    EventoFinanceiroItem,
    GrupoAvaliacaoQualidade,
    MedicaoItemCompetencia,
    ModeloAvaliacaoQualidade,
    OcorrenciaContrato,
    OcorrenciaContratoAnexo,
    ResponsavelEmpresa,
    TermoAditivo,
)
from .services import numero_contrato_por_ano, parse_numero_contrato


User = get_user_model()
BOOTSTRAP_INPUT = 'form-control form-control-lg'
BOOTSTRAP_TEXTAREA = 'form-control spi-textarea-compact'


def validar_upload_pdf(arquivo):
    """Aceita apenas PDF nos fluxos em que o documento precisa ser visualizado no modal."""

    if not arquivo:
        return arquivo
    nome = (getattr(arquivo, 'name', '') or '').lower()
    content_type = (getattr(arquivo, 'content_type', '') or '').lower()
    if not nome.endswith('.pdf') or content_type not in {'application/pdf', 'application/x-pdf'}:
        raise ValidationError('Envie um arquivo PDF válido.')
    return arquivo


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes visuais padronizadas aos widgets do módulo."""

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
            current = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{current} {css}'.strip()


class UsuarioPerfilChoiceField(forms.ModelChoiceField):
    """Mostra nome completo do perfil quando disponível nas listas de usuários internos."""

    def label_from_instance(self, obj):
        perfil = getattr(obj, 'perfil', None)
        nome = perfil.nome_completo if perfil and perfil.nome_completo else obj.get_full_name() or obj.username
        return f'{nome} ({obj.username})'


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
            'apelido',
            'objeto',
            'data_inicio_vigencia',
            'prazo_inicial_meses',
            'vigencia_maxima_meses',
            'empresa_contratada',
            'fiscal_administrativo',
            'fiscal_tecnico',
            'gestor_contrato',
            'base_mensal',
            'situacao_forcada',
        ]

    def _incremental_requested(self):
        """Lê diretamente o POST para decidir se o número será gerado automaticamente."""

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
            # Na edição mantemos o número atual livre para ajuste manual sem exibir a automação inicial.
            self.fields['numero_contrato_incremental'].initial = False
        else:
            # No cadastro, o backend pode preencher o número ao salvar quando o modo incremental estiver ativo.
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
        return cleaned


class ContratoItemForm(BootstrapModelForm):
    """Formulário de item do contrato com ordem opcional para preenchimento automático."""

    class Meta:
        model = ContratoItem
        fields = [
            'ordem',
            'descricao',
            'codigo_siafisico',
            'codigo_catmat_catser',
            'unidade_fornecimento',
            'quantidade',
            'valor_unitario',
            'valor_referencial',
        ]
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A ordem é sugerida automaticamente pela view; o usuário pode ajustar se precisar.
        self.fields['ordem'].required = False
        self.fields['ordem'].help_text = 'Se deixar em branco, o sistema usará o próximo número disponível.'


class ContratoDetalhamentoItemForm(BootstrapModelForm):
    """Linha do detalhamento estruturado do objeto contratual."""

    class Meta:
        model = ContratoDetalhamentoItem
        fields = ['ordem', 'descricao']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


ContratoDetalhamentoItemFormSet = inlineformset_factory(
    Contrato,
    ContratoDetalhamentoItem,
    form=ContratoDetalhamentoItemForm,
    extra=0,
    can_delete=True,
)


class TermoAditivoForm(BootstrapModelForm):
    class Meta:
        model = TermoAditivo
        fields = [
            'numero_termo',
            'tipo',
            'data_assinatura',
            'data_inicio',
            'data_termino',
            'quantidade_meses',
            'justificativa',
            'documento_anexo',
        ]
        widgets = {'justificativa': forms.Textarea(attrs={'rows': 4})}


class DocumentoContratoForm(BootstrapModelForm):
    DOCUMENTOS_PREDEFINIDOS = [
        ('DFD_PCA', 'Documento Formalizador da Demanda do PCA'),
        ('DFD_CONTRATACAO', 'Documento Formalizador da Demanda da Contratação'),
        ('ETP', 'Estudo Técnico Preliminar'),
        ('MATRIZ_RISCO', 'Matriz de Risco'),
        ('TERMO_REFERENCIA', 'Termo de Referência'),
        ('PARECER_CJ', 'Parecer CJ'),
        ('CONTRATO', 'Contrato'),
    ]
    MAPA_TIPO_DESCRICAO = {
        'DFD_PCA': (DocumentoContrato.Tipo.OUTRO, 'Documento Formalizador da Demanda do PCA'),
        'DFD_CONTRATACAO': (DocumentoContrato.Tipo.OUTRO, 'Documento Formalizador da Demanda da Contratação'),
        'ETP': (DocumentoContrato.Tipo.OUTRO, 'Estudo Técnico Preliminar'),
        'MATRIZ_RISCO': (DocumentoContrato.Tipo.OUTRO, 'Matriz de Risco'),
        'TERMO_REFERENCIA': (DocumentoContrato.Tipo.OUTRO, 'Termo de Referência'),
        'PARECER_CJ': (DocumentoContrato.Tipo.PARECER, 'Parecer CJ'),
        'CONTRATO': (DocumentoContrato.Tipo.CONTRATO, 'Contrato'),
    }
    documento_predefinido = forms.ChoiceField(label='Documento', choices=DOCUMENTOS_PREDEFINIDOS)

    class Meta:
        model = DocumentoContrato
        fields = ['documento_predefinido', 'arquivo', 'data_documento']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tipo e descrição passam a ser derivados do documento pré-estabelecido.
        self.fields['documento_predefinido'].widget.attrs['class'] = 'form-select form-select-lg'

    def save(self, commit=True):
        instancia = super().save(commit=False)
        tipo, descricao = self.MAPA_TIPO_DESCRICAO[self.cleaned_data['documento_predefinido']]
        instancia.tipo = tipo
        instancia.descricao = descricao
        if commit:
            instancia.save()
        return instancia


class OcorrenciaContratoForm(BootstrapModelForm):
    class Meta:
        model = OcorrenciaContrato
        fields = ['data_registro', 'hora_registro', 'tipo_ocorrencia', 'descricao']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 4})}


class OcorrenciaContratoAnexoForm(BootstrapModelForm):
    class Meta:
        model = OcorrenciaContratoAnexo
        fields = ['arquivo', 'nome_exibicao']


class CompetenciaPagamentoForm(BootstrapModelForm):
    class Meta:
        model = CompetenciaPagamento
        fields = ['periodo_inicio', 'periodo_fim', 'nota_fiscal', 'status', 'data_efetivacao']


class CompetenciaPagamentoExecucaoForm(BootstrapModelForm):
    """Conclui o pagamento da competência por meio dos três anexos obrigatórios."""

    class Meta:
        model = CompetenciaPagamento
        fields = ['anexo_nota_fiscal', 'anexo_atestado_realizacao', 'anexo_despacho_dof']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['anexo_nota_fiscal'].label = 'Nota Fiscal'
        self.fields['anexo_atestado_realizacao'].label = 'Atestado de Realização'
        self.fields['anexo_despacho_dof'].label = 'Despacho DOF'
        for field_name in ('anexo_nota_fiscal', 'anexo_atestado_realizacao', 'anexo_despacho_dof'):
            self.fields[field_name].widget.attrs['accept'] = 'application/pdf,.pdf'

    def clean_anexo_nota_fiscal(self):
        return validar_upload_pdf(self.cleaned_data.get('anexo_nota_fiscal'))

    def clean_anexo_atestado_realizacao(self):
        return validar_upload_pdf(self.cleaned_data.get('anexo_atestado_realizacao'))

    def clean_anexo_despacho_dof(self):
        return validar_upload_pdf(self.cleaned_data.get('anexo_despacho_dof'))


class ChecklistPagamentoModeloForm(BootstrapModelForm):
    """Checklist padrão do contrato com índice totalmente automático."""

    class Meta:
        model = ChecklistPagamentoModelo
        fields = ['titulo', 'descricao', 'obrigatorio']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


class ChecklistPagamentoItemForm(BootstrapModelForm):
    class Meta:
        model = ChecklistPagamentoItem
        fields = ['concluido']


class ChecklistPagamentoAnexoForm(BootstrapModelForm):
    class Meta:
        model = ChecklistPagamentoAnexo
        fields = ['arquivo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['arquivo'].widget.attrs['accept'] = 'application/pdf,.pdf'

    def clean_arquivo(self):
        return validar_upload_pdf(self.cleaned_data.get('arquivo'))


class CompetenciaMedicaoLoteForm(forms.Form):
    """Monta a tabela mensal de medição trazendo os itens do contrato para preenchimento das quantidades."""

    def __init__(self, *args, contrato=None, competencia=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contrato = contrato
        self.competencia = competencia
        self.itens = list((contrato.itens.order_by('ordem', 'id') if contrato is not None else []))
        medicoes_existentes = {}
        if competencia is not None:
            medicoes_existentes = {
                medicao.item_contrato_id: medicao
                for medicao in competencia.medicoes.select_related('item_contrato')
            }

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


class MedicaoItemCompetenciaForm(BootstrapModelForm):
    class Meta:
        model = MedicaoItemCompetencia
        fields = ['item_contrato', 'quantidade', 'valor_unitario_aplicado', 'observacoes']
        widgets = {'observacoes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, contrato=None, **kwargs):
        super().__init__(*args, **kwargs)
        if contrato is not None:
            self.fields['item_contrato'].queryset = contrato.itens.order_by('ordem', 'id')


class ModeloAvaliacaoQualidadeForm(BootstrapModelForm):
    class Meta:
        model = ModeloAvaliacaoQualidade
        fields = ['nome', 'vigencia_inicio', 'vigencia_fim', 'ativo']


class GrupoAvaliacaoQualidadeForm(BootstrapModelForm):
    class Meta:
        model = GrupoAvaliacaoQualidade
        fields = ['ordem', 'nome', 'peso']


class CriterioAvaliacaoQualidadeForm(BootstrapModelForm):
    class Meta:
        model = CriterioAvaliacaoQualidade
        fields = ['ordem', 'nome', 'descricao', 'peso', 'pontuacao_maxima']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 3})}


class AvaliacaoQualidadeCompetenciaForm(BootstrapModelForm):
    class Meta:
        model = AvaliacaoQualidadeCompetencia
        fields = ['modelo', 'observacoes']
        widgets = {'observacoes': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, contrato=None, **kwargs):
        super().__init__(*args, **kwargs)
        if contrato is not None:
            self.fields['modelo'].queryset = contrato.modelos_qualidade.filter(ativo=True).order_by('-vigencia_inicio', '-id')


class AvaliacaoCriterioCompetenciaForm(BootstrapModelForm):
    class Meta:
        model = AvaliacaoCriterioCompetencia
        fields = ['criterio', 'nota_obtida', 'observacoes']
        widgets = {'observacoes': forms.Textarea(attrs={'rows': 2})}

    def __init__(self, *args, modelo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if modelo is not None:
            self.fields['criterio'].queryset = CriterioAvaliacaoQualidade.objects.filter(grupo__modelo=modelo).order_by(
                'grupo__ordem', 'ordem', 'id'
            )


class EventoFinanceiroContratoForm(BootstrapModelForm):
    class Meta:
        model = EventoFinanceiroContrato
        fields = [
            'tipo',
            'indice_aplicado',
            'data_base',
            'data_aplicacao',
            'percentual_aplicado',
            'justificativa',
            'historico',
            'documento_anexo',
        ]
        widgets = {
            'justificativa': forms.Textarea(attrs={'rows': 3}),
            'historico': forms.Textarea(attrs={'rows': 3}),
        }


class EventoFinanceiroItemForm(BootstrapModelForm):
    class Meta:
        model = EventoFinanceiroItem
        fields = ['item_contrato', 'valor_original', 'valor_reajustado', 'valor_referencial']

    def __init__(self, *args, contrato=None, **kwargs):
        super().__init__(*args, **kwargs)
        if contrato is not None:
            self.fields['item_contrato'].queryset = contrato.itens.order_by('ordem', 'id')
