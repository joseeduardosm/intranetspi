import re
import os

filepath = '/root/aplicacoesspi/contratos/views.py'
with open(filepath, 'r') as f:
    c = f.read()

import_json = "from django.http import JsonResponse\nfrom .forms import numero_contrato_por_ano\n"

view_code = """
@login_required
def proximo_numero_contrato(request):
    ano = request.GET.get('ano')
    if not ano or not ano.isdigit() or len(ano) != 4:
        return JsonResponse({'numero': ''}, status=400)
    
    numero = numero_contrato_por_ano(int(ano))
    return JsonResponse({'numero': numero})
"""

if "def proximo_numero_contrato" not in c:
    c = c.replace('from django.shortcuts import get_object_or_404, redirect, render', 
                  'from django.shortcuts import get_object_or_404, redirect, render\n' + import_json)
    c += '\n' + view_code + '\n'

with open(filepath, 'w') as f:
    f.write(c)
