# Criado por José Eduardo Santana Martins em 04/06/2026

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from functools import wraps
from .utils import obter_nivel_acesso, RANK_PERMISSAO
from .models import RegraAcesso


class ACLRequiredMixin(UserPassesTestMixin):
    """
    Mixin para views do Django que valida o nível de acesso (Leitura, Modificação, Controle Total).
    Exemplo:
        recurso_slug = 'licitacoes'
    """
    recurso_slug = None

    # Define qual o nível mínimo exigido para entrar nesta view específica.
    # Por padrão, apenas estar autenticado e ter permissão de Leitura (ou qualquer nível) basta.
    # Views de criar/editar/excluir podem sobrescrever para 'MODIFICACAO' ou 'CONTROLE_TOTAL'.
    acl_nivel_minimo = RegraAcesso.NIVEL_LEITURA

    def get_acl_level(self):
        # Calcula o nível uma única vez por requisição da view e reutiliza no contexto.
        if not hasattr(self, '_acl_level'):
            self._acl_level = obter_nivel_acesso(self.request.user, self.recurso_slug)
        return self._acl_level

    def test_func(self):
        # Views sem recurso configurado permanecem liberadas para preservar compatibilidade.
        if not self.recurso_slug:
            return True
            
        nivel_atual = self.get_acl_level()
        if not nivel_atual:
            return False

        # Verifica se o nível atual atende ao nível mínimo exigido
        rank_atual = RANK_PERMISSAO.get(nivel_atual, 0)
        rank_minimo = RANK_PERMISSAO.get(self.acl_nivel_minimo, 0)
        
        if rank_atual < rank_minimo:
            return False

        # Se for nível MODIFICACAO em uma View de Edição/Exclusão, verifica se o usuário é o dono
        # do objeto. Assume que o objeto possui um atributo 'criado_por' ou 'usuario'.
        if nivel_atual == RegraAcesso.NIVEL_MODIFICACAO and self.request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            obj = getattr(self, 'object', None) or (self.get_object() if hasattr(self, 'get_object') else None)
            if obj:
                # Tenta localizar o campo de propriedade do registro
                dono = getattr(obj, 'criado_por', None) or getattr(obj, 'user', None) or getattr(obj, 'usuario', None)
                if dono and dono != self.request.user:
                    raise PermissionDenied("Você só pode modificar registros que você mesmo criou.")

        return True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Disponibiliza o nível e flags de acesso no template HTML
        nivel = self.get_acl_level()
        context['acl_level'] = nivel
        context['acl_pode_escrever'] = nivel in (RegraAcesso.NIVEL_MODIFICACAO, RegraAcesso.NIVEL_CONTROLE_TOTAL)
        context['acl_controle_total'] = (nivel == RegraAcesso.NIVEL_CONTROLE_TOTAL)
        return context


def acl_required(recurso_slug, nivel_minimo=RegraAcesso.NIVEL_LEITURA):
    """
    Decorator para views baseadas em função que restringe acesso com base no nível mínimo.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Replica a mesma hierarquia do mixin para views baseadas em função.
            nivel_atual = obter_nivel_acesso(request.user, recurso_slug)
            if not nivel_atual:
                raise PermissionDenied("Acesso negado pelas regras de ACL.")
                
            rank_atual = RANK_PERMISSAO.get(nivel_atual, 0)
            rank_minimo = RANK_PERMISSAO.get(nivel_minimo, 0)
            
            if rank_atual < rank_minimo:
                raise PermissionDenied("Seu nível de permissão não atende aos requisitos desta página.")
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
