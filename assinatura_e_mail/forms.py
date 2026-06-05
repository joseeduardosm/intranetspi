# Criado por José Eduardo Santana Martins em 04/06/2026
# Objetivo: Definir o formulário usado para coletar os dados da assinatura institucional.

from django import forms


# Classe padrão aplicada aos campos para manter o visual Bootstrap do formulário.
BOOTSTRAP_INPUT = 'form-control form-control-lg'


class AssinaturaEmailForm(forms.Form):
    """Coleta dados pessoais e institucionais usados na imagem da assinatura."""

    nome_completo = forms.CharField(label='Nome completo', max_length=220)
    cargo_funcao = forms.CharField(label='Cargo/Função', max_length=180)
    departamento = forms.CharField(label='Departamento', max_length=180, required=False)
    email = forms.EmailField(label='E-mail', max_length=254)
    ramal = forms.CharField(label='Ramal', max_length=40, required=False)
    celular = forms.CharField(label='Celular', max_length=40, required=False)
    data_nascimento = forms.DateField(
        label='Data de nascimento',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Aplica classes visuais aos widgets sem sobrescrever classes já definidas.
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{existing} {BOOTSTRAP_INPUT}'.strip()

