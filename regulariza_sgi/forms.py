# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir formulários de imóveis, anexos, SEI e eventos do ciclo processual.

from django import forms

from .models import CicloProcessual, Imovel, ImovelAnexo, ImovelProcessoSEI
from .services import municipio_choices


BOOTSTRAP_INPUT = 'form-control'
BOOTSTRAP_SELECT = 'form-select'


class BootstrapModelForm(forms.ModelForm):
    """Aplica classes Bootstrap aos campos conforme o widget."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = BOOTSTRAP_SELECT
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

    class Meta:
        model = Imovel
        fields = [
            'inscricao_imobiliaria',
            'matricula',
            'processo_judicial',
            'numero_sgi',
            'uf',
            'municipio',
            'logradouro',
            'bairro',
            'numero',
            'area',
            'possui_cadin',
            'exercicio_cadin',
            'notificacao_cadin_municipal',
        ]
        widgets = {
            'area': forms.NumberInput(attrs={'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Municípios dependem da UF selecionada e são atualizados também no frontend.
        uf = self.data.get('uf') or getattr(self.instance, 'uf', 'SP') or 'SP'
        self.fields['municipio'].widget = forms.Select(attrs={'class': BOOTSTRAP_SELECT})
        self.fields['municipio'].choices = [('', 'Selecione')] + municipio_choices(uf)
        self.fields['exercicio_cadin'].help_text = 'Exemplo: 2023 ou 2017 à 2023.'
        self.fields['notificacao_cadin_municipal'].help_text = 'Informe o número ou identificação da notificação.'
        self.fields['numero'].help_text = 'Pode ser preenchido com S/N.'

    def clean(self):
        cleaned = super().clean()
        # O bloco CADIN exige dados de cobrança; sem CADIN, os campos são limpos.
        possui_cadin = cleaned.get('possui_cadin')
        exercicio = (cleaned.get('exercicio_cadin') or '').strip()
        notificacao = (cleaned.get('notificacao_cadin_municipal') or '').strip()
        if possui_cadin and not exercicio:
            self.add_error('exercicio_cadin', 'Informe o exercício da cobrança de IPTU.')
        if possui_cadin and not notificacao:
            self.add_error('notificacao_cadin_municipal', 'Informe a notificação CADIN municipal.')
        if not possui_cadin:
            cleaned['exercicio_cadin'] = ''
            cleaned['notificacao_cadin_municipal'] = ''
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
