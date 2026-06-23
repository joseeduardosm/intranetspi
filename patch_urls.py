filepath = '/root/aplicacoesspi/contratos/urls.py'
with open(filepath, 'r') as f:
    c = f.read()

import_code = "    path('proximo-numero/', views.proximo_numero_contrato, name='proximo_numero_contrato'),\n"

if "proximo-numero" not in c:
    c = c.replace("path('novo/', views.ContratoCreateView.as_view(), name='contrato_create'),", 
                  "path('novo/', views.ContratoCreateView.as_view(), name='contrato_create'),\n" + import_code)

with open(filepath, 'w') as f:
    f.write(c)
