filepath = '/root/aplicacoesspi/contratos/views.py'
with open(filepath, 'r') as f:
    c = f.read()

if "from django.contrib.auth.decorators import login_required" not in c:
    c = c.replace("from django.http import JsonResponse", "from django.http import JsonResponse\nfrom django.contrib.auth.decorators import login_required")

with open(filepath, 'w') as f:
    f.write(c)
