# Criado por José Eduardo Santana Martins em 04/06/2026

from .models import Recurso, RegraAcesso

# Hierarquia de permissões: Controle Total > Modificação > Leitura
RANK_PERMISSAO = {
    RegraAcesso.NIVEL_LEITURA: 1,
    RegraAcesso.NIVEL_MODIFICACAO: 2,
    RegraAcesso.NIVEL_CONTROLE_TOTAL: 3,
}

def obter_nivel_acesso(user, app_slug):
    """
    Verifica o nível de acesso de um usuário para um determinado app/recurso.
    Retorna 'LEITURA', 'MODIFICACAO', 'CONTROLE_TOTAL' ou None (Sem Acesso).
    """
    if user.is_anonymous:
        return None

    # Superusuários e administradores sempre têm Controle Total
    if user.is_superuser or user.is_staff:
        return RegraAcesso.NIVEL_CONTROLE_TOTAL

    try:
        recurso = Recurso.objects.get(slug=app_slug)
    except Recurso.DoesNotExist:
        # Se o recurso/app não está registrado, acesso padrão é Controle Total (Opt-out)
        return RegraAcesso.NIVEL_CONTROLE_TOTAL

    regras = RegraAcesso.objects.filter(recurso=recurso)

    # Sem regras cadastradas, o recurso permanece aberto para não bloquear módulos por acidente.
    if not regras.exists():
        return RegraAcesso.NIVEL_CONTROLE_TOTAL

    # Regras individuais têm prioridade sobre regras herdadas por grupo/setor.
    regras_usuario = regras.filter(usuario=user)
    if regras_usuario.exists():
        # Retorna o nível da regra individual (se houver mais de uma, pega a maior)
        niveis = [r.nivel for r in regras_usuario]
        maior_nivel = max(niveis, key=lambda n: RANK_PERMISSAO.get(n, 0))
        return maior_nivel

    # Na ausência de regra individual, usa o maior nível disponível nos grupos do usuário.
    user_groups = user.groups.all()
    if user_groups.exists():
        regras_grupo = regras.filter(grupo__in=user_groups)
        if regras_grupo.exists():
            # Obtém a de maior privilégio entre os grupos que o usuário pertence
            niveis = [r.nivel for r in regras_grupo]
            maior_nivel = max(niveis, key=lambda n: RANK_PERMISSAO.get(n, 0))
            return maior_nivel

    # Se o app possui regras mas o usuário não se encaixa em nenhuma, ele não tem acesso.
    return None
