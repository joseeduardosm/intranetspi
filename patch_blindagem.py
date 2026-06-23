import re
import sys

filepath = '/root/aplicacoesspi/contratos/views.py'
with open(filepath, 'r') as f:
    c = f.read()

mixin_code = """
from django.contrib import messages
from django.shortcuts import redirect

class BlockIfCompetenciasGeradasMixin:
    \"\"\"Bloqueia a edição/exclusão de itens estruturais se as competências já foram geradas.\"\"\"
    def dispatch(self, request, *args, **kwargs):
        obj = None
        if hasattr(self, 'get_object'):
            try:
                # Some views might need pk, but kwargs has it
                if 'pk' in kwargs or 'slug' in kwargs:
                    obj = self.get_object()
            except:
                pass
        
        contrato = None
        if obj:
            if hasattr(obj, 'competencias'):  # it's a Contrato
                contrato = obj
            elif hasattr(obj, 'contrato'):
                contrato = obj.contrato
            elif hasattr(obj, 'modelo_checklist'):
                contrato = obj.modelo_checklist.contrato
            elif hasattr(obj, 'formulario'):
                contrato = obj.formulario.contrato
            elif hasattr(obj, 'grupo'):
                contrato = obj.grupo.formulario.contrato
        
        if not contrato:
            from .models import Contrato, ChecklistModelo, FormularioAvaliacao, GrupoAvaliacao
            if 'contrato_pk' in kwargs:
                contrato = Contrato.objects.filter(pk=kwargs['contrato_pk']).first()
            elif 'modelo_pk' in kwargs:
                modelo = ChecklistModelo.objects.filter(pk=kwargs['modelo_pk']).first()
                if modelo: contrato = modelo.contrato
            elif 'formulario_pk' in kwargs:
                form = FormularioAvaliacao.objects.filter(pk=kwargs['formulario_pk']).first()
                if form: contrato = form.contrato
            elif 'grupo_pk' in kwargs:
                grupo = GrupoAvaliacao.objects.filter(pk=kwargs['grupo_pk']).first()
                if grupo: contrato = grupo.formulario.contrato
        
        if contrato and contrato.competencias.exists():
            messages.error(request, 'Ação bloqueada: Este contrato já possui competências geradas. Nenhuma alteração estrutural é permitida.')
            return redirect('contratos:contrato_detail', pk=contrato.pk)
            
        return super().dispatch(request, *args, **kwargs)
"""

if "BlockIfCompetenciasGeradasMixin" not in c:
    c = c.replace("from django.views.generic import ", mixin_code + "\nfrom django.views.generic import ")

# Classes to patch
classes_to_patch = [
    "ContratoUpdateView",
    "ContratoDeleteView",
    "ContratoItemCreateView",
    "ContratoItemUpdateView",
    "ContratoItemDeleteView",
    "ChecklistModeloCreateView",
    "ChecklistModeloUpdateView",
    "ChecklistModeloDeleteView",
    "ChecklistModeloItemCreateView",
    "ChecklistModeloItemUpdateView",
    "ChecklistModeloItemDeleteView",
    "FormularioAvaliacaoCreateView",
    "FormularioAvaliacaoUpdateView",
    "FormularioAvaliacaoDeleteView",
    "EscalaNotaAvaliacaoCreateView",
    "EscalaNotaAvaliacaoUpdateView",
    "EscalaNotaAvaliacaoDeleteView",
    "FaixaLiberacaoAvaliacaoCreateView",
    "FaixaLiberacaoAvaliacaoUpdateView",
    "FaixaLiberacaoAvaliacaoDeleteView",
    "GrupoAvaliacaoCreateView",
    "GrupoAvaliacaoUpdateView",
    "GrupoAvaliacaoDeleteView",
    "ItemAvaliacaoCreateView",
    "ItemAvaliacaoUpdateView",
    "ItemAvaliacaoDeleteView",
]

for cls in classes_to_patch:
    # Look for class ContratoUpdateView(BaseMixin, UpdateView):
    # or class ContratoUpdateView(UpdateView):
    # or class ContratoItemCreateView(LoginRequiredMixin, CreateView):
    pattern = rf"class {cls}\((.+?)\):"
    
    def replacer(match):
        bases = match.group(1)
        if "BlockIfCompetenciasGeradasMixin" not in bases:
            return f"class {cls}(BlockIfCompetenciasGeradasMixin, {bases}):"
        return match.group(0)
    
    c = re.sub(pattern, replacer, c)

with open(filepath, 'w') as f:
    f.write(c)

