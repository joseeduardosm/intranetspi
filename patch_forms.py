filepath = '/root/aplicacoesspi/contratos/forms.py'
with open(filepath, 'r') as f:
    c = f.read()

import_str = "from contratos_old.forms import validar_upload_pdf"

func_code = """
from django.core.exceptions import ValidationError

def validar_upload_pdf(arquivo):
    if not arquivo:
        return arquivo
    nome = (getattr(arquivo, 'name', '') or '').lower()
    content_type = (getattr(arquivo, 'content_type', '') or '').lower()
    if not nome.endswith('.pdf') or content_type not in {'application/pdf', 'application/x-pdf'}:
        raise ValidationError('Envie um arquivo PDF válido.')
    return arquivo
"""

if import_str in c:
    c = c.replace(import_str, func_code)

with open(filepath, 'w') as f:
    f.write(c)
