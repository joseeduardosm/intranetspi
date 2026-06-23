import re

with open('contratos_old/views.py', 'r') as f:
    views_content = f.read()

with open('contratos_old/forms.py', 'r') as f:
    forms_content = f.read()

# Extrair EmpresaListView até EmpresaDeleteView
views_match = re.search(r'(class EmpresaListView.*?)class ContratoListView', views_content, re.DOTALL)
if views_match:
    with open('contratos/views.py', 'a') as f:
        f.write('\n\n' + views_match.group(1).replace('contratos_old', 'contratos'))

# Extrair EmpresaContratadaForm e ResponsavelEmpresaForm
forms_match = re.search(r'(class EmpresaContratadaForm.*?)class ContratoForm', forms_content, re.DOTALL)
if forms_match:
    with open('contratos/forms.py', 'a') as f:
        f.write('\n\n' + forms_match.group(1))

# Adicionar URLs
urls_to_add = """
    path('empresas/', views.EmpresaListView.as_view(), name='empresa_list'),
    path('empresas/nova/', views.EmpresaCreateView.as_view(), name='empresa_create'),
    path('empresas/<int:pk>/editar/', views.EmpresaUpdateView.as_view(), name='empresa_update'),
    path('empresas/<int:pk>/excluir/', views.EmpresaDeleteView.as_view(), name='empresa_delete'),
    path('empresas/<int:empresa_pk>/responsavel/novo/', views.ResponsavelEmpresaCreateView.as_view(), name='responsavel_create'),
"""

with open('contratos/urls.py', 'r') as f:
    urls_content = f.read()

if 'empresas/' not in urls_content:
    urls_content = urls_content.replace('urlpatterns = [', 'urlpatterns = [\n' + urls_to_add)
    with open('contratos/urls.py', 'w') as f:
        f.write(urls_content)

