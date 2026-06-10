# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir formulários de imóveis, anexos, SEI e eventos do ciclo processual.

from decimal import Decimal, InvalidOperation

from django import forms

from .models import CicloProcessual, Imovel, ImovelAnexo, ImovelObservacao, ImovelProcessoSEI
from .services import municipio_choices


BOOTSTRAP_INPUT = 'form-control'
BOOTSTRAP_SELECT = 'form-select'


def decimal_to_brl(value):
    """Converte decimal para o formato brasileiro usado nos campos monetários."""

    if value in (None, ''):
        return ''
    inteiro, fracionario = f'{Decimal(value):.2f}'.split('.')
    inteiro_formatado = f'{int(inteiro):,}'.replace(',', '.')
    return f'{inteiro_formatado},{fracionario}'


class BrlDecimalField(forms.DecimalField):
    """Aceita entrada monetária no padrão brasileiro e devolve Decimal limpo."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, Decimal):
            return value
        normalized = str(value).strip().replace('.', '').replace(',', '.')
        try:
            return Decimal(normalized)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError('Informe um valor monetário válido.')


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes Bootstrap aos campos conforme o widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = BOOTSTRAP_SELECT
            elif isinstance(field.widget, forms.RadioSelect):
                css = 'regulariza-radio-group'
            elif isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(field.widget, forms.Textarea):
                css = 'form-control'
            else:
                css = BOOTSTRAP_INPUT
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {css}'.strip()


class ImovelForm(BootstrapModelForm):
    """Formulário principal de cadastro e edição do imóvel."""

    imunidade = forms.TypedChoiceField(
        label='Imunidade',
        choices=(('sim', 'Sim'), ('nao', 'Não')),
        coerce=lambda value: value in {True, 'True', 'true', '1', 'sim', 'on'},
        widget=forms.RadioSelect,
    )
    dividas_nao_ajuizadas = BrlDecimalField(
        label='Dívidas não ajuizadas',
        required=False,
        max_digits=14,
        decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'data-money-field': 'true', 'placeholder': '0,00'}),
    )
    dividas_ajuizadas = BrlDecimalField(
        label='Dívidas ajuizadas',
        required=False,
        max_digits=14,
        decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'data-money-field': 'true', 'placeholder': '0,00'}),
    )
    encargos = BrlDecimalField(
        label='Encargos',
        required=False,
        max_digits=14,
        decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'data-money-field': 'true', 'placeholder': '0,00'}),
    )

    class Meta:
        model = Imovel
        fields = [
            'inscricao_imobiliaria',
            'matricula',
            'numero_sgi',
            'sei',
            'link_sei',
            'logradouro',
            'uf',
            'municipio',
            'bairro',
            'area',
            'processo_judicial',
            'imissao_posse',
            'imunidade',
            'tempo_imunidade',
            'exercicio_cobranca',
            'divida_ativa',
            'numero_divida',
            'dividas_nao_ajuizadas',
            'dividas_ajuizadas',
            'encargos',
        ]
        widgets = {
            'area': forms.NumberInput(attrs={'step': '0.01'}),
            'imissao_posse': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'tempo_imunidade': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Municípios dependem da UF selecionada e são atualizados também no frontend.
        uf = self.data.get('uf') or getattr(self.instance, 'uf', 'SP') or 'SP'
        municipio_atual = self.data.get('municipio') or getattr(self.instance, 'municipio', 'São Paulo') or 'São Paulo'
        self.fields['inscricao_imobiliaria'].label = 'Cadastro SQL'
        self.fields['municipio'].widget = forms.Select(attrs={'class': BOOTSTRAP_SELECT})
        municipio_options = municipio_choices(uf)
        if municipio_atual and (municipio_atual, municipio_atual) not in municipio_options:
            # Mantém municípios legados editáveis mesmo quando não estão na lista fechada atual.
            municipio_options = municipio_options + [(municipio_atual, municipio_atual)]
        self.fields['municipio'].choices = [('', 'Selecione')] + municipio_options
        self.fields['uf'].initial = self.initial.get('uf') or getattr(self.instance, 'uf', 'SP') or 'SP'
        self.fields['municipio'].initial = self.initial.get('municipio') or municipio_atual
        self.fields['tempo_imunidade'].help_text = 'Informe o tempo em anos.'
        self.fields['area'].required = False
        self.fields['numero_sgi'].required = False
        self.fields['sei'].required = False
        self.fields['link_sei'].required = False
        self.fields['imissao_posse'].required = False
        self.fields['tempo_imunidade'].required = False
        self.fields['exercicio_cobranca'].required = False
        self.fields['divida_ativa'].required = False
        self.fields['numero_divida'].required = False
        self.fields['dividas_nao_ajuizadas'].required = False
        self.fields['dividas_ajuizadas'].required = False
        self.fields['encargos'].required = False
        for campo_monetario in ('dividas_nao_ajuizadas', 'dividas_ajuizadas', 'encargos'):
            valor = self.initial.get(campo_monetario)
            if valor in (None, '') and getattr(self.instance, 'pk', None):
                valor = getattr(self.instance, campo_monetario)
            self.initial[campo_monetario] = decimal_to_brl(valor)
        if not self.is_bound:
            self.initial.setdefault('uf', 'SP')
            self.initial.setdefault('municipio', 'São Paulo')
            self.initial.setdefault('imunidade', 'sim' if getattr(self.instance, 'imunidade', False) else 'nao')

    def clean(self):
        cleaned = super().clean()
        # A interface exibe o tempo da imunidade somente quando o usuário marca "sim".
        imunidade = cleaned.get('imunidade')
        tempo = cleaned.get('tempo_imunidade')
        if imunidade and not tempo:
            self.add_error('tempo_imunidade', 'Informe o tempo de imunidade.')
        if not imunidade:
            cleaned['tempo_imunidade'] = None
        return cleaned


class ProcessoSEIForm(BootstrapModelForm):
    """Formulário de processo SEI associado ao imóvel."""

    class Meta:
        model = ImovelProcessoSEI
        fields = ['numero_sei', 'link_sei']


class ImovelAnexoForm(BootstrapModelForm):
    """Formulário de anexo do imóvel."""

    class Meta:
        model = ImovelAnexo
        fields = ['nome_exibicao', 'arquivo']


class ImovelObservacaoForm(BootstrapModelForm):
    """Formulário enxuto para inclusão inline de observações do imóvel."""

    class Meta:
        model = ImovelObservacao
        fields = ['texto']
        widgets = {
            'texto': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Registre uma observação relevante sobre o imóvel.'}),
        }


class ProtocoloForm(forms.Form):
    """Coleta os dados que iniciam a contagem de resposta da prefeitura."""

    numero_protocolo = forms.CharField(label='Número do protocolo', max_length=120, widget=forms.TextInput(attrs={'class': BOOTSTRAP_INPUT}))
    data_protocolo = forms.DateField(
        label='Data do protocolo',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': BOOTSTRAP_INPUT}),
    )
    prazo_resposta_dias = forms.IntegerField(
        label='Prazo de resposta da prefeitura (dias)',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT}),
    )


class ProrrogacaoForm(forms.Form):
    """Coleta prorrogação do prazo de resposta do ciclo atual."""

    prorrogacao_dias = forms.IntegerField(
        label='Prorrogação (dias)',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT}),
    )
    data_prorrogacao = forms.DateField(
        label='Data da prorrogação',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': BOOTSTRAP_INPUT}),
    )


class ManifestacaoForm(forms.Form):
    """Coleta manifestação da prefeitura e prazo de imunidade quando deferida."""

    resultado = forms.ChoiceField(
        label='Resultado',
        choices=CicloProcessual.Resultado.choices,
        widget=forms.RadioSelect,
    )
    data_manifestacao = forms.DateField(
        label='Data da manifestação',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': BOOTSTRAP_INPUT}),
    )
    prazo_imunidade_anos = forms.IntegerField(
        label='Prazo da imunidade (anos)',
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT}),
    )

    def clean(self):
        cleaned = super().clean()
        # Deferimento precisa de prazo para calcular vencimento e renovação.
        if cleaned.get('resultado') == CicloProcessual.Resultado.DEFERIDO and not cleaned.get('prazo_imunidade_anos'):
            self.add_error('prazo_imunidade_anos', 'Informe o prazo da imunidade.')
        if cleaned.get('resultado') != CicloProcessual.Resultado.DEFERIDO:
            cleaned['prazo_imunidade_anos'] = None
        return cleaned
