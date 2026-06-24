# Criado por OpenAI Codex em 23/06/2026
# Centraliza regras de pesquisa, progresso temporal, status e histórico do módulo.

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from setores.models import SetorNode, UserSetorMembership
from setores.services import primary_setor_for_user

from .forms import user_display_name
from .models import Tarefa, TarefaHistorico

User = get_user_model()


# Mapa oficial do documento funcional para transformar prioridade em peso numérico.
PRIORIDADE_CARGA_PESOS = {
    Tarefa.Prioridade.CRITICA: 8,
    Tarefa.Prioridade.ALTA: 5,
    Tarefa.Prioridade.NORMAL: 3,
    Tarefa.Prioridade.BAIXA: 1,
}

STATUS_OPERACIONAIS = (
    Tarefa.Status.PENDENTE,
    Tarefa.Status.EM_ANDAMENTO,
    Tarefa.Status.CONCLUIDA,
)

HISTORICO_FILTROS = {
    "": None,
    "TUDO": None,
    "COMENTARIOS": {TarefaHistorico.TipoEvento.COMENTARIO},
    "ALTERACOES": {
        TarefaHistorico.TipoEvento.EDICAO,
        TarefaHistorico.TipoEvento.ALTERACAO_PRAZO,
        TarefaHistorico.TipoEvento.ALTERACAO_STATUS,
        TarefaHistorico.TipoEvento.CONCLUSAO,
        TarefaHistorico.TipoEvento.REABERTURA,
    },
    "SISTEMA": {
        TarefaHistorico.TipoEvento.CRIACAO,
        TarefaHistorico.TipoEvento.ARQUIVAMENTO_AUTOMATICO,
    },
    "ANEXOS": {TarefaHistorico.TipoEvento.ANEXO},
}


def registrar_historico(
    *,
    tarefa,
    autor,
    tipo_evento,
    titulo_evento,
    descricao_evento="",
    comentario="",
    arquivo=None,
    prazo_anterior=None,
    prazo_novo=None,
):
    """Cria um item cronológico único no universo da tarefa."""

    historico = TarefaHistorico(
        tarefa=tarefa,
        autor=autor,
        tipo_evento=tipo_evento,
        titulo_evento=titulo_evento,
        descricao_evento=descricao_evento,
        comentario=comentario,
        prazo_anterior=prazo_anterior,
        prazo_novo=prazo_novo,
    )
    if arquivo:
        historico.arquivo = arquivo
        historico.nome_arquivo = getattr(arquivo, "name", "") or ""
    historico.save()
    return historico


def formatar_duracao_humana(delta):
    """Traduz diferença temporal em texto compacto amigável para a interface."""

    total_segundos = max(int(delta.total_seconds()), 0)
    dias, resto = divmod(total_segundos, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, _ = divmod(resto, 60)
    partes = []
    if dias:
        partes.append(f"{dias}d")
    if horas or dias:
        partes.append(f"{horas}h")
    partes.append(f"{minutos}min")
    return " ".join(partes)


def calcular_progresso_prazo_tarefa(tarefa, referencia=None):
    """Calcula a barra temporal de uma tarefa a partir de criação até o prazo final."""

    referencia = referencia or timezone.now()
    inicio = tarefa.criado_em
    fim = tarefa.prazo
    total_segundos = max((fim - inicio).total_seconds(), 1)
    consumido_segundos = max((referencia - inicio).total_seconds(), 0)
    percentual_real = (consumido_segundos / total_segundos) * 100
    percentual = max(0, min(percentual_real, 100))
    atrasada = referencia > fim

    if atrasada:
        return {
            "percentual": 100.0,
            "percentual_real": round(percentual_real, 1),
            "cor": "danger-strong",
            "atrasada": True,
            "texto": f"Atrasada há {formatar_duracao_humana(referencia - fim)}",
        }
    if percentual <= 50:
        cor = "success"
    elif percentual <= 74.9:
        cor = "warning"
    else:
        cor = "danger"
    return {
        "percentual": round(percentual, 1),
        "percentual_real": round(percentual_real, 1),
        "cor": cor,
        "atrasada": False,
        "texto": f"{round(percentual, 1)}% do prazo consumido",
    }


def enriquecer_tarefa_para_interface(tarefa, referencia=None):
    """Anexa dados derivados usados pela tabela, kanban e detalhe."""

    progresso = calcular_progresso_prazo_tarefa(tarefa, referencia=referencia)
    tarefa.progresso_prazo = progresso
    tarefa.autor_nome = user_display_name(tarefa.criado_por)
    tarefa.responsavel_nome = user_display_name(tarefa.responsavel)
    return tarefa


def ordenar_queryset_tarefas(queryset, order_by="prazo", direction="asc"):
    """Aplica ordenação server-side segura com mapeamento explícito."""

    ordering_map = {
        "id": "id",
        "titulo": "titulo",
        "prazo": "prazo",
        "criado_por": "criado_por__perfil__nome_completo",
        "responsavel": "responsavel__perfil__nome_completo",
        "atualizado_em": "atualizado_em",
    }
    campo = ordering_map.get(order_by, "prazo")
    prefixo = "-" if direction == "desc" else ""
    return queryset.order_by(f"{prefixo}{campo}", f"{prefixo}id")


def queryset_macro_usuario(user, termo="", prioridade="", status="", order_by="prazo", direction="asc"):
    """Filtra e ordena as tarefas pessoais, incluindo histórico e nomes envolvidos."""

    queryset = Tarefa.objects.do_usuario(user).select_related("criado_por__perfil", "responsavel__perfil")
    termo = (termo or "").strip()
    prioridade = (prioridade or "").strip().upper()
    status = (status or "").strip().upper()
    id_filter = Q()
    if prioridade in Tarefa.Prioridade.values:
        queryset = queryset.filter(prioridade=prioridade)
    if status in Tarefa.Status.values:
        queryset = queryset.filter(status=status)
    if termo.isdigit():
        id_filter = Q(id=int(termo))
    if termo:
        queryset = queryset.filter(
            id_filter
            | Q(titulo__icontains=termo)
            | Q(descricao__icontains=termo)
            | Q(criado_por__username__icontains=termo)
            | Q(criado_por__perfil__nome_completo__icontains=termo)
            | Q(responsavel__username__icontains=termo)
            | Q(responsavel__perfil__nome_completo__icontains=termo)
            | Q(historico__titulo_evento__icontains=termo)
            | Q(historico__descricao_evento__icontains=termo)
            | Q(historico__comentario__icontains=termo)
            | Q(historico__nome_arquivo__icontains=termo)
        ).distinct()
    return ordenar_queryset_tarefas(queryset, order_by=order_by, direction=direction)


def queryset_historico_tarefa(tarefa, termo="", filtro=""):
    """Permite pesquisar e segmentar somente o universo cronológico da tarefa."""

    queryset = tarefa.historico.select_related("autor__perfil")
    termo = (termo or "").strip()
    filtro = (filtro or "").strip().upper()
    tipos = HISTORICO_FILTROS.get(filtro)
    if tipos:
        queryset = queryset.filter(tipo_evento__in=tipos)
    if termo:
        queryset = queryset.filter(
            Q(titulo_evento__icontains=termo)
            | Q(descricao_evento__icontains=termo)
            | Q(comentario__icontains=termo)
            | Q(nome_arquivo__icontains=termo)
        )
    return queryset


def multiplicador_urgencia_tarefa(tarefa, referencia=None):
    """Aplica o multiplicador temporal do documento com base no prazo atual."""

    referencia = referencia or timezone.now()
    delta = tarefa.prazo - referencia
    if delta.total_seconds() < 0:
        return 4
    if delta < timedelta(days=3):
        return 3
    if delta <= timedelta(days=7):
        return 2
    if delta <= timedelta(days=15):
        return 1.5
    return 1


def calcular_pontuacao_carga_tarefa(tarefa, referencia=None):
    """Retorna a pontuação individual da tarefa segundo prioridade e urgência."""

    if tarefa.status == Tarefa.Status.ARQUIVADA:
        return 0
    peso_prioridade = PRIORIDADE_CARGA_PESOS.get(tarefa.prioridade, 0)
    multiplicador = multiplicador_urgencia_tarefa(tarefa, referencia=referencia)
    return peso_prioridade * multiplicador


def classificar_faixa_ocupacao(carga_total):
    """Traduz a pontuação total em uma faixa amigável para a interface."""

    if carga_total <= 20:
        return {"rotulo": "Baixa ocupação", "cor": "success", "icone": "🟢"}
    if carga_total <= 40:
        return {"rotulo": "Ocupação moderada", "cor": "warning", "icone": "🟡"}
    if carga_total <= 60:
        return {"rotulo": "Alta ocupação", "cor": "orange", "icone": "🟠"}
    return {"rotulo": "Sobrecarga crítica", "cor": "danger", "icone": "🔴"}


def calcular_resumo_carga_usuario(queryset, referencia=None):
    """Calcula a carga agregada do usuário para uso na visão macro."""

    referencia = referencia or timezone.now()
    tarefas = [tarefa for tarefa in list(queryset) if tarefa.status != Tarefa.Status.ARQUIVADA]
    carga_total = sum(calcular_pontuacao_carga_tarefa(tarefa, referencia=referencia) for tarefa in tarefas)
    return {
        "carga_total": carga_total,
        "faixa_ocupacao": classificar_faixa_ocupacao(carga_total),
        "atrasadas": sum(1 for tarefa in tarefas if tarefa.prazo < referencia),
    }


def descrever_transicao_status(status_anterior, status_novo):
    """Produz rótulo textual consistente para auditoria das transições."""

    mapa = {
        Tarefa.Status.PENDENTE: "Pendente",
        Tarefa.Status.EM_ANDAMENTO: "Em andamento",
        Tarefa.Status.CONCLUIDA: "Concluída",
        Tarefa.Status.ARQUIVADA: "Arquivada",
    }
    return f"Status alterado de {mapa.get(status_anterior, status_anterior)} para {mapa.get(status_novo, status_novo)}."


def mover_tarefa_status(*, tarefa, novo_status, autor):
    """Aplica transição de status válida, atualiza datas e registra histórico."""

    novo_status = (novo_status or "").strip().upper()
    if novo_status not in STATUS_OPERACIONAIS:
        raise ValidationError("Status inválido para movimentação manual.")
    if tarefa.status == Tarefa.Status.ARQUIVADA:
        raise ValidationError("Tarefas arquivadas não podem ser movidas pelo kanban.")

    transicoes = {
        Tarefa.Status.PENDENTE: {Tarefa.Status.EM_ANDAMENTO},
        Tarefa.Status.EM_ANDAMENTO: {Tarefa.Status.PENDENTE, Tarefa.Status.CONCLUIDA},
        Tarefa.Status.CONCLUIDA: {Tarefa.Status.PENDENTE, Tarefa.Status.EM_ANDAMENTO},
    }
    if novo_status == tarefa.status:
        return tarefa
    if novo_status not in transicoes.get(tarefa.status, set()):
        raise ValidationError("Transição de status não permitida.")

    status_anterior = tarefa.status
    tarefa.status = novo_status
    evento = TarefaHistorico.TipoEvento.ALTERACAO_STATUS
    titulo = "Status atualizado"
    descricao = descrever_transicao_status(status_anterior, novo_status)
    if novo_status == Tarefa.Status.CONCLUIDA:
        tarefa.concluida_em = timezone.now()
        evento = TarefaHistorico.TipoEvento.CONCLUSAO
        titulo = "Tarefa concluída"
    elif status_anterior == Tarefa.Status.CONCLUIDA and novo_status in {Tarefa.Status.PENDENTE, Tarefa.Status.EM_ANDAMENTO}:
        tarefa.concluida_em = None
        evento = TarefaHistorico.TipoEvento.REABERTURA
        titulo = "Tarefa reaberta"
    else:
        tarefa.concluida_em = None if novo_status != Tarefa.Status.CONCLUIDA else tarefa.concluida_em
    tarefa.save(update_fields=["status", "concluida_em", "atualizado_em"])
    registrar_historico(
        tarefa=tarefa,
        autor=autor,
        tipo_evento=evento,
        titulo_evento=titulo,
        descricao_evento=descricao,
    )
    return tarefa


def arquivar_tarefas_concluidas(*, referencia=None):
    """Arquiva tarefas concluídas há mais de 3 dias de maneira idempotente."""

    referencia = referencia or timezone.now()
    limite = referencia - timedelta(days=3)
    tarefas = list(
        Tarefa.objects.filter(status=Tarefa.Status.CONCLUIDA, concluida_em__isnull=False, concluida_em__lte=limite)
    )
    for tarefa in tarefas:
        tarefa.status = Tarefa.Status.ARQUIVADA
        tarefa.save(update_fields=["status", "atualizado_em"])
        registrar_historico(
            tarefa=tarefa,
            autor=None,
            tipo_evento=TarefaHistorico.TipoEvento.ARQUIVAMENTO_AUTOMATICO,
            titulo_evento="Tarefa arquivada automaticamente",
            descricao_evento="A tarefa permaneceu concluída por mais de 3 dias e foi arquivada automaticamente.",
        )
    return len(tarefas)


def listar_liderados_imediatos(gestor):
    """Retorna somente o primeiro nível hierárquico por superior imediato."""

    return (
        User.objects.filter(is_active=True, perfil__superior_imediato=gestor)
        .select_related("perfil")
        .order_by("perfil__nome_completo", "username")
    )


def listar_subordinados_em_arvore(gestor):
    """Resolve toda a árvore subordinada por superior imediato, sem duplicidade."""

    encontrados = []
    visitados = set()
    fila = list(listar_liderados_imediatos(gestor))
    while fila:
        usuario = fila.pop(0)
        if usuario.id in visitados:
            continue
        visitados.add(usuario.id)
        encontrados.append(usuario)
        fila.extend(list(listar_liderados_imediatos(usuario)))
    return encontrados


def listar_usuarios_do_setor_ou_coordenacao(gestor):
    """Obtém usuários da ramificação do setor principal do gestor."""

    setor = primary_setor_for_user(gestor)
    if not setor:
        return []
    ids = _coletar_ids_setor_subarvore(setor)
    return _usuarios_por_setores(ids)


def listar_usuarios_da_diretoria(gestor):
    """Obtém usuários da diretoria/ramo superior do setor principal do gestor."""

    setor = primary_setor_for_user(gestor)
    if not setor:
        return []
    raiz = setor
    while raiz.parent_id:
        raiz = raiz.parent
    ids = _coletar_ids_setor_subarvore(raiz)
    return _usuarios_por_setores(ids)


def gestor_tem_visao_gerencial(gestor):
    """Indica se o usuário pode acessar o dashboard de equipe."""

    return bool(
        listar_liderados_imediatos(gestor).exists()
        or SetorNode.objects.filter(ativo=True, lider=gestor).exists()
        or UserSetorMembership.objects.filter(setor__lider=gestor).exists()
    )


def resolver_escopo_gerencial(gestor, scope="imediatos"):
    """Retorna usuários visíveis e metadados do escopo gerencial solicitado."""

    scope = (scope or "imediatos").strip().lower()
    if scope == "arvore":
        usuarios = listar_subordinados_em_arvore(gestor)
        rotulo = "Toda a estrutura subordinada"
    elif scope == "setor":
        usuarios = listar_usuarios_do_setor_ou_coordenacao(gestor)
        rotulo = "Setor / Coordenação"
    elif scope == "diretoria":
        usuarios = listar_usuarios_da_diretoria(gestor)
        rotulo = "Diretoria"
    else:
        usuarios = list(listar_liderados_imediatos(gestor))
        scope = "imediatos"
        rotulo = "Subordinados imediatos"
    usuarios_filtrados = []
    vistos = set()
    for usuario in usuarios:
        if usuario.id == gestor.id or usuario.id in vistos:
            continue
        vistos.add(usuario.id)
        usuarios_filtrados.append(usuario)
    return {"scope": scope, "label": rotulo, "usuarios": usuarios_filtrados}


def montar_card_gerencial_usuario(usuario, referencia=None):
    """Monta payload resumido para cards e cabeçalhos gerenciais."""

    queryset = queryset_macro_usuario(usuario)
    resumo = calcular_resumo_carga_usuario(queryset, referencia=referencia)
    total_operacionais = queryset.exclude(status=Tarefa.Status.ARQUIVADA).count()
    progresso_percentual = min(resumo["carga_total"], 100)
    return {
        "usuario": usuario,
        "nome": user_display_name(usuario),
        "cargo": getattr(usuario.perfil, "cargo", "") if hasattr(usuario, "perfil") else "",
        "setor": getattr(usuario.perfil, "setor", "") if hasattr(usuario, "perfil") else "",
        "total_operacionais": total_operacionais,
        "carga_total": resumo["carga_total"],
        "faixa_ocupacao": resumo["faixa_ocupacao"],
        "progress_percentual": progresso_percentual,
        "resumo": resumo,
        "tem_subordinados": listar_liderados_imediatos(usuario).exists(),
    }


def montar_cards_gerenciais(usuarios, referencia=None):
    """Cria cards de equipe ordenados por carga decrescente e nome."""

    cards = [montar_card_gerencial_usuario(usuario, referencia=referencia) for usuario in usuarios]
    return sorted(cards, key=lambda item: (-item["carga_total"], item["nome"].lower()))


def montar_cadeia_hierarquica_usuario(usuario, *, limite=10):
    """Monta a trilha hierárquica ascendente para uso em breadcrumbs gerenciais."""

    cadeia = []
    atual = usuario
    visitados = set()
    while atual and atual.id not in visitados and len(cadeia) < limite:
        visitados.add(atual.id)
        cadeia.append(atual)
        perfil = getattr(atual, "perfil", None)
        atual = getattr(perfil, "superior_imediato", None)
    cadeia.reverse()
    return cadeia


def gestor_pode_ver_usuario(gestor, alvo):
    """Controla se o alvo está dentro de algum escopo gerencial do gestor."""

    if gestor.id == alvo.id:
        return True
    for scope in ("imediatos", "arvore", "setor", "diretoria"):
        ids = {usuario.id for usuario in resolver_escopo_gerencial(gestor, scope)["usuarios"]}
        if alvo.id in ids:
            return True
    return False


def _coletar_ids_setor_subarvore(setor):
    """Percorre a árvore do setor para montar a sub-ramificação institucional."""

    visitados = set()
    fila = [setor]
    while fila:
        atual = fila.pop(0)
        if atual.id in visitados:
            continue
        visitados.add(atual.id)
        fila.extend(list(atual.children.filter(ativo=True).select_related("group", "parent")))
    return visitados


def _usuarios_por_setores(setor_ids):
    """Retorna usuários distintos vinculados aos setores informados."""

    memberships = (
        UserSetorMembership.objects.filter(setor_id__in=setor_ids, user__is_active=True)
        .select_related("user__perfil")
        .order_by("user__perfil__nome_completo", "user__username")
    )
    vistos = set()
    usuarios = []
    for membership in memberships:
        if membership.user_id in vistos:
            continue
        vistos.add(membership.user_id)
        usuarios.append(membership.user)
    return usuarios
