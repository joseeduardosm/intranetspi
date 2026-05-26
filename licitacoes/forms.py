import re

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import (
    Dfd,
    DfdItemTabela,
    EtpTic,
    Fornecedor,
    ItemEtpTic,
    ItemTR,
    PesquisaPreco,
    PesquisaPrecoFornecedor,
    SessaoEtpTic,
    SessaoTR,
    TabelaItemLinha,
    TermoReferencia,
)
from .services import DFD_SECOES_MAP, ETP_TIC_SECOES_MAP


BOOTSTRAP_INPUT = 'form-control form-control-lg'
BOOTSTRAP_TEXTAREA = 'form-control spi-textarea-compact'


class BootstrapModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                css = 'form-select form-select-lg'
            elif isinstance(field.widget, forms.Textarea):
                css = BOOTSTRAP_TEXTAREA
            else:
                css = BOOTSTRAP_INPUT
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {css}'.strip()


class EtpTicCreateForm(BootstrapModelForm):
    class Meta:
        model = EtpTic
        fields = ['nome', 'numero_processo', 'link']


class EtpTicSecaoForm(BootstrapModelForm):
    class Meta:
        model = EtpTic
        fields = '__all__'
        widgets = {
            'descricao_necessidade': forms.Textarea(attrs={'rows': 10}),
            'necessidades_negocio': forms.Textarea(attrs={'rows': 10}),
            'necessidades_tecnologicas': forms.Textarea(attrs={'rows': 10}),
            'demais_requisitos': forms.Textarea(attrs={'rows': 10}),
            'estimativa_demanda': forms.Textarea(attrs={'rows': 10}),
            'levantamento_solucoes': forms.Textarea(attrs={'rows': 10}),
            'analise_comparativa_solucoes': forms.Textarea(attrs={'rows': 10}),
            'solucoes_inviaveis': forms.Textarea(attrs={'rows': 10}),
            'analise_comparativa_custos_tco': forms.Textarea(attrs={'rows': 10}),
            'descricao_solucao_tic': forms.Textarea(attrs={'rows': 10}),
            'estimativa_custo_texto': forms.Textarea(attrs={'rows': 10}),
            'justificativa_tecnica': forms.Textarea(attrs={'rows': 10}),
            'justificativa_economica': forms.Textarea(attrs={'rows': 10}),
            'beneficios_contratacao': forms.Textarea(attrs={'rows': 10}),
            'providencias_adotadas': forms.Textarea(attrs={'rows': 10}),
            'declaracao_viabilidade': forms.Textarea(attrs={'rows': 4}),
            'justificativa_viabilidade': forms.Textarea(attrs={'rows': 10}),
        }

    def __init__(self, *args, section_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = set(section_fields or [])
        for name in list(self.fields):
            if name not in allowed:
                self.fields.pop(name)
        if 'declaracao_viabilidade' in self.fields:
            self.fields['declaracao_viabilidade'].disabled = True


class DfdCreateForm(BootstrapModelForm):
    class Meta:
        model = Dfd
        fields = ['nome', 'numero_processo']


class DfdSecaoForm(BootstrapModelForm):
    class Meta:
        model = Dfd
        fields = '__all__'
        widgets = {
            'informacoes_preliminares': forms.Textarea(attrs={'rows': 10}),
            'descricao_objeto': forms.Textarea(attrs={'rows': 10}),
            'objeto_nao_luxo': forms.Textarea(attrs={'rows': 4}),
            'justificativa_necessidade': forms.Textarea(attrs={'rows': 10}),
            'estimativa_quantidade_valores': forms.Textarea(attrs={'rows': 10}),
            'vinculacao_outro_dfd': forms.Textarea(attrs={'rows': 10}),
            'responsaveis': forms.Textarea(attrs={'rows': 10}),
        }

    def __init__(self, *args, section_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed = set(section_fields or [])
        for name in list(self.fields):
            if name not in allowed:
                self.fields.pop(name)


class DfdItemTabelaForm(BootstrapModelForm):
    class Meta:
        model = DfdItemTabela
        fields = [
            'especificacao',
            'catmat',
            'siafisico',
            'unidade_medida',
            'quantidade',
            'valor_unitario',
            'valor_total',
        ]
        widgets = {'especificacao': forms.Textarea(attrs={'rows': 6})}


class TermoReferenciaForm(BootstrapModelForm):
    class Meta:
        model = TermoReferencia
        fields = ['nome', 'numero_processo', 'link']


class SessaoTRForm(BootstrapModelForm):
    class Meta:
        model = SessaoTR
        fields = ['titulo']


class SessaoEtpTicForm(BootstrapModelForm):
    class Meta:
        model = SessaoEtpTic
        fields = ['titulo']


class ItemTRForm(BootstrapModelForm):
    class Meta:
        model = ItemTR
        fields = ['texto']
        widgets = {'texto': forms.Textarea(attrs={'rows': 12})}

    def clean_texto(self):
        texto = (self.cleaned_data.get('texto') or '').strip()
        texto = re.sub(r'^\s*\d+(?:\.\d+)+(?:\.)?\s*[-–—:]?\s*', '', texto)
        texto = re.sub(r'^\s*(?:[IVXLCDM]+|[a-z])\)\s*', '', texto, flags=re.IGNORECASE)
        return texto


class ItemEtpTicForm(BootstrapModelForm):
    class Meta:
        model = ItemEtpTic
        fields = ['texto']
        widgets = {'texto': forms.Textarea(attrs={'rows': 12})}

    def clean_texto(self):
        texto = (self.cleaned_data.get('texto') or '').strip()
        return re.sub(r'^\s*\d+(?:\.\d+)+(?:\.)?\s*[-–—:]?\s*', '', texto)


class TabelaItemLinhaForm(BootstrapModelForm):
    class Meta:
        model = TabelaItemLinha
        fields = ['descricao', 'catmat_catser', 'siafisico', 'unidade_fornecimento', 'quantidade']
        widgets = {'descricao': forms.Textarea(attrs={'rows': 10})}


class PesquisaPrecoCreateForm(BootstrapModelForm):
    class Meta:
        model = PesquisaPreco
        fields = ['pesquisador_nome', 'pesquisador_email', 'pesquisador_cargo', 'tipo', 'vigencia_meses']

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        vigencia = cleaned.get('vigencia_meses')
        if tipo == PesquisaPreco.Tipo.SERVICO and not vigencia:
            self.add_error('vigencia_meses', 'Informe a vigência em meses para serviços.')
        if tipo == PesquisaPreco.Tipo.AQUISICAO:
            cleaned['vigencia_meses'] = None
        return cleaned


class FornecedorForm(BootstrapModelForm):
    class Meta:
        model = Fornecedor
        fields = ['razao_social', 'cnpj', 'telefone', 'contato', 'email_contato']
        help_texts = {
            'email_contato': 'Para informar mais de um e-mail, separe por ponto e vírgula.',
        }

    def clean_email_contato(self):
        value = (self.cleaned_data.get('email_contato') or '').strip()
        emails = [email.strip() for email in value.split(';') if email.strip()]
        if not emails:
            raise ValidationError('Informe pelo menos um e-mail do contato.')
        invalidos = []
        for email in emails:
            try:
                validate_email(email)
            except ValidationError:
                invalidos.append(email)
        if invalidos:
            raise ValidationError(f'E-mail inválido: {", ".join(invalidos)}.')
        return '; '.join(emails)


class PesquisaPrecoFornecedorForm(forms.Form):
    fornecedor = forms.ModelChoiceField(
        label='Fornecedor',
        queryset=Fornecedor.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'}),
    )

    def __init__(self, *args, pesquisa=None, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = Fornecedor.objects.all()
        if pesquisa:
            queryset = queryset.exclude(pesquisas_preco__pesquisa=pesquisa)
        self.fields['fornecedor'].queryset = queryset


class PesquisaPrecoOrcamentoForm(forms.Form):
    data_resposta = forms.DateField(
        label='Data da resposta',
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'class': BOOTSTRAP_INPUT}),
    )
    validade_orcamento_dias = forms.IntegerField(
        label='Validade do orçamento em dias',
        min_value=1,
        widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT}),
    )
    documento_fornecedor = forms.FileField(
        label='Documento do fornecedor',
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': BOOTSTRAP_INPUT}),
    )

    def __init__(self, *args, itens=None, valores=None, has_document=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.itens = list(itens or [])
        self.has_document = has_document
        valores = valores or {}
        for item in self.itens:
            name = self.item_field_name(item)
            self.fields[name] = forms.DecimalField(
                label=f'Item {item.ordem} - Preço unitário',
                min_value=0,
                max_digits=14,
                decimal_places=2,
                initial=valores.get(item.id),
                widget=forms.NumberInput(attrs={'class': BOOTSTRAP_INPUT, 'step': '0.01'}),
            )

    @staticmethod
    def item_field_name(item):
        return f'preco_item_{item.id}'

    def clean_documento_fornecedor(self):
        documento = self.cleaned_data.get('documento_fornecedor')
        if not documento and not self.has_document:
            raise forms.ValidationError('Anexe o documento do fornecedor para salvar o orçamento.')
        return documento


class ItemMoveForm(forms.Form):
    target = forms.CharField(label='Destino', required=True)
    action = forms.ChoiceField(
        label='Acao',
        choices=[
            ('after', 'Mover apos o item destino'),
            ('child', 'Mover como subitem do item destino'),
        ],
    )
    child_position = forms.IntegerField(
        label='Posicao dentro do destino',
        min_value=1,
        required=False,
        help_text='Use somente ao mover como subitem. Deixe vazio para inserir no final.',
    )

    def __init__(self, *args, termo=None, item=None, action_label='Mover', **kwargs):
        super().__init__(*args, **kwargs)
        action_label = action_label.strip()
        action_lower = action_label.lower()
        choices = []
        blocked = {item.id} if item else set()
        if item:
            from .services import item_descendant_ids

            blocked |= item_descendant_ids(item)
        for sessao in termo.sessoes.order_by('ordem', 'id'):
            choices.append((f'sessao:{sessao.id}', f'{sessao.ordem}. {sessao.titulo}'))
            for row in __import__('licitacoes.services', fromlist=['build_item_rows']).build_item_rows(sessao):
                row_item = row['item']
                if row_item.id in blocked:
                    continue
                prefix = '' if row.get('is_subsecao') else row['enum_prefix'] or f"{row['indice']}."
                label = f"{'  ' * row['depth']}{prefix} {row_item.texto[:100]}"
                choices.append((f'item:{row_item.id}', label))
        self.fields['target'].widget = forms.Select(choices=choices, attrs={'class': 'form-select form-select-lg'})
        self.fields['action'].choices = [
            ('after', f'{action_label} apos o item destino'),
            ('child', f'{action_label} como subitem do item destino'),
        ]
        self.fields['action'].widget.attrs.update({'class': 'form-select form-select-lg'})
        self.fields['child_position'].widget.attrs.update({
            'class': BOOTSTRAP_INPUT,
            'placeholder': 'Ex.: 1',
        })
        self.session_action_error = f'Para {action_lower} para uma sessao, use a opcao de subitem/raiz do destino.'

    def clean(self):
        cleaned = super().clean()
        target = cleaned.get('target') or ''
        action = cleaned.get('action')
        if target.startswith('sessao:') and action != 'child':
            raise forms.ValidationError(self.session_action_error)
        return cleaned


class ItemEtpMoveForm(forms.Form):
    target = forms.CharField(label='Destino', required=True)
    action = forms.ChoiceField(
        label='Acao',
        choices=[
            ('after', 'Mover apos o item destino'),
            ('child', 'Mover como subitem do item destino'),
        ],
    )
    child_position = forms.IntegerField(
        label='Posicao dentro do destino',
        min_value=1,
        required=False,
        help_text='Use somente ao mover como subitem. Deixe vazio para inserir no final.',
    )

    def __init__(self, *args, etp=None, item=None, action_label='Mover', **kwargs):
        super().__init__(*args, **kwargs)
        action_label = action_label.strip()
        action_lower = action_label.lower()
        choices = []
        blocked = {item.id} if item else set()
        if item:
            from .services import etp_item_descendant_ids

            blocked |= etp_item_descendant_ids(item)
        for sessao in etp.sessoes.order_by('ordem', 'id'):
            choices.append((f'sessao:{sessao.id}', f'{sessao.ordem}. {sessao.titulo}'))
            for row in __import__('licitacoes.services', fromlist=['build_etp_item_rows']).build_etp_item_rows(sessao):
                row_item = row['item']
                if row_item.id in blocked:
                    continue
                prefix = '' if row.get('is_subsecao') else row.get('enum_prefix') or f"{row['indice']}."
                label = f"{'  ' * row['depth']}{prefix} {row_item.texto[:100]}"
                choices.append((f'item:{row_item.id}', label))
        self.fields['target'].widget = forms.Select(choices=choices, attrs={'class': 'form-select form-select-lg'})
        self.fields['action'].choices = [
            ('after', f'{action_label} apos o item destino'),
            ('child', f'{action_label} como subitem do item destino'),
        ]
        self.fields['action'].widget.attrs.update({'class': 'form-select form-select-lg'})
        self.fields['child_position'].widget.attrs.update({
            'class': BOOTSTRAP_INPUT,
            'placeholder': 'Ex.: 1',
        })
        self.session_action_error = f'Para {action_lower} para uma sessao, use a opcao de subitem/raiz do destino.'

    def clean(self):
        cleaned = super().clean()
        target = cleaned.get('target') or ''
        action = cleaned.get('action')
        if target.startswith('sessao:') and action != 'child':
            raise forms.ValidationError(self.session_action_error)
        return cleaned


def form_for_etp_section(numero, *args, **kwargs):
    kwargs['section_fields'] = ETP_TIC_SECOES_MAP[numero]['campos']
    return EtpTicSecaoForm(*args, **kwargs)


def form_for_dfd_section(numero, *args, **kwargs):
    kwargs['section_fields'] = DFD_SECOES_MAP[numero]['campos']
    return DfdSecaoForm(*args, **kwargs)
