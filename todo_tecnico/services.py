# Criado por OpenAI Codex em 20/06/2026
# Objetivo: Centralizar a fila, o agendamento e a integração do To-Do Técnico com o Codex CLI.

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import CodexConfiguracao, CodexExecucao, TarefaTecnica


LOCK_PATH = Path(tempfile.gettempdir()) / "todo_tecnico_codex_worker.lock"


@dataclass
class JanelaUso:
    """Estrutura simples usada pelo painel de monitoramento da página principal."""

    limite: int
    consumido: int
    restante: int
    percentual_restante: float
    redefinicao_em: timezone.datetime | None


@dataclass
class ConsumoCodex:
    """Representa o consumo consolidado do Codex em uma janela temporal."""

    consumido: int
    redefinicao_em: timezone.datetime | None


def get_codex_configuracao() -> CodexConfiguracao:
    """Recupera a configuração única do executor."""

    return CodexConfiguracao.get_solo()


def _caminho_state_codex(configuracao: CodexConfiguracao) -> Path:
    """Resolve o banco local do Codex que armazena threads e tokens usados."""

    return Path(configuracao.codex_home).expanduser() / "state_5.sqlite"


def _thread_pertence_ao_workspace(cwd: str, workspace: str) -> bool:
    """Aceita sessões abertas no próprio projeto, em subpastas ou em diretórios-pai do projeto."""

    cwd_resolvido = str(Path(cwd).resolve())
    workspace_resolvido = str(Path(workspace).resolve())
    return (
        cwd_resolvido == workspace_resolvido
        or cwd_resolvido.startswith(workspace_resolvido + "/")
        or workspace_resolvido.startswith(cwd_resolvido + "/")
    )


def normalizar_titulo_tarefa(tarefa: TarefaTecnica) -> str:
    """Gera um título legível quando a tarefa ainda não possui um resumo adequado."""

    titulo = (tarefa.titulo or "").strip()
    if len(titulo) >= 12:
        return titulo

    primeira_linha = next((linha.strip() for linha in tarefa.descricao.splitlines() if linha.strip()), "")
    if not primeira_linha:
        return f"Tarefa técnica #{tarefa.pk}"

    primeira_linha = primeira_linha.rstrip(".")
    if len(primeira_linha) <= 90:
        return primeira_linha[:1].upper() + primeira_linha[1:]
    return f"{primeira_linha[:87].rstrip()}..."


def montar_prompt_execucao(execucao: CodexExecucao, configuracao: CodexConfiguracao) -> str:
    """Constrói um prompt consistente para execuções manuais e agendadas."""

    tarefa = execucao.tarefa
    titulo_base = normalizar_titulo_tarefa(tarefa)
    momento = "agendada" if execucao.tipo == CodexExecucao.TIPO_AGENDADA else "manual"

    return textwrap.dedent(
        f"""
        Você está executando uma tarefa do módulo To-Do Técnico em um projeto Django localizado em `{configuracao.workspace_path}`.

        Tipo de disparo: {momento}
        Identificador da tarefa: #{tarefa.pk}
        Título atual: {titulo_base}

        Descrição completa:
        {tarefa.descricao}

        Instruções fixas obrigatórias:
        {configuracao.instrucoes_fixas}

        Requisitos operacionais adicionais:
        - Faça a implementação diretamente no repositório local.
        - Use português brasileiro em textos visíveis ao usuário.
        - Preserve os padrões do projeto e evite abstrações desnecessárias.
        - Rode apenas validações e testes proporcionais ao risco da alteração.
        - Se precisar criar migrações, deixe o código pronto para `makemigrations` e `migrate`.
        - Ao terminar, responda estritamente no JSON do schema fornecido.

        Campos esperados na resposta final:
        - titulo_final: título melhorado da tarefa.
        - solucao_curta: resumo curto e elucidativo da solução aplicada.
        - resumo_alteracoes: resumo objetivo do que foi alterado.
        - testes_executados: texto curto com os testes ou checks realizados.
        - observacoes: riscos residuais, pendências ou "Nenhuma" se não houver.
        """
    ).strip()


def _consumo_codex_por_threads(configuracao: CodexConfiguracao, desde: timezone.datetime, duracao: timedelta) -> ConsumoCodex | None:
    """Lê o consumo real do Codex a partir do estado local do CLI por workspace."""

    state_path = _caminho_state_codex(configuracao)
    if not state_path.exists():
        return None

    workspace = str(Path(configuracao.workspace_path).resolve())
    since_ts = int(desde.timestamp())
    consulta = """
        select cwd, tokens_used, created_at
        from threads
        where created_at >= ?
    """

    try:
        conexao = sqlite3.connect(f"file:{state_path}?mode=ro", uri=True)
        try:
            cursor = conexao.execute(consulta, [since_ts])
            linhas = cursor.fetchall()
        finally:
            conexao.close()
    except sqlite3.Error:
        return None

    linhas_workspace = [linha for linha in linhas if _thread_pertence_ao_workspace(linha[0], workspace)]
    consumido = int(sum(int(linha[1] or 0) for linha in linhas_workspace))
    primeira_execucao_ts = min((int(linha[2]) for linha in linhas_workspace), default=None)
    redefinicao_em = None
    if primeira_execucao_ts:
        redefinicao_em = timezone.datetime.fromtimestamp(
            int(primeira_execucao_ts),
            tz=timezone.get_current_timezone(),
        ) + duracao
    return ConsumoCodex(consumido=consumido, redefinicao_em=redefinicao_em)


def _consumo_codex_por_execucoes(duracao: timedelta, desde: timezone.datetime) -> ConsumoCodex:
    """Mantém compatibilidade com o consumo medido apenas pelas execuções internas do módulo."""

    agregados = CodexExecucao.objects.filter(
        status=CodexExecucao.STATUS_CONCLUIDA,
        iniciado_em__gte=desde,
    ).aggregate(total=Sum("total_tokens"))
    primeira_execucao = (
        CodexExecucao.objects.filter(
            status=CodexExecucao.STATUS_CONCLUIDA,
            iniciado_em__gte=desde,
            total_tokens__gt=0,
        )
        .order_by("iniciado_em")
        .first()
    )
    redefinicao_em = primeira_execucao.iniciado_em + duracao if primeira_execucao and primeira_execucao.iniciado_em else None
    return ConsumoCodex(consumido=int(agregados["total"] or 0), redefinicao_em=redefinicao_em)


def calcular_janela_uso(configuracao: CodexConfiguracao, limite: int, desde: timezone.datetime, duracao: timedelta) -> JanelaUso:
    """Consolida o consumo de tokens em uma janela móvel para o painel lateral."""

    consumo = _consumo_codex_por_threads(configuracao, desde, duracao) or _consumo_codex_por_execucoes(duracao, desde)
    restante = max(limite - consumo.consumido, 0)
    percentual_restante = 0.0 if limite <= 0 else round((restante / limite) * 100, 1)
    return JanelaUso(
        limite=limite,
        consumido=consumo.consumido,
        restante=restante,
        percentual_restante=percentual_restante,
        redefinicao_em=consumo.redefinicao_em,
    )


def obter_monitoramento_codex(configuracao: CodexConfiguracao) -> dict[str, JanelaUso]:
    """Gera os indicadores exibidos no painel lateral do módulo."""

    agora = timezone.now()
    return {
        "janela_5h": calcular_janela_uso(
            configuracao,
            configuracao.limite_tokens_5h,
            agora - timedelta(hours=5),
            timedelta(hours=5),
        ),
        "janela_semanal": calcular_janela_uso(
            configuracao,
            configuracao.limite_tokens_semanal,
            agora - timedelta(days=7),
            timedelta(days=7),
        ),
    }


def listar_execucoes_painel() -> dict[str, object]:
    """Organiza a fila e o histórico recente para a coluna lateral."""

    pendentes = list(
        CodexExecucao.objects.select_related("tarefa")
        .filter(status__in=[CodexExecucao.STATUS_AGENDADA, CodexExecucao.STATUS_NA_FILA, CodexExecucao.STATUS_EM_EXECUCAO])
        .order_by("status", "agendado_para", "criado_em")[:8]
    )
    recentes = list(
        CodexExecucao.objects.select_related("tarefa")
        .filter(status__in=[CodexExecucao.STATUS_CONCLUIDA, CodexExecucao.STATUS_ERRO])
        .order_by("-finalizado_em", "-id")[:8]
    )
    return {
        "pendentes": pendentes,
        "recentes": recentes,
        "existe_pendente": any(execucao.aguardando_processamento for execucao in pendentes),
    }


def enfileirar_execucao(tarefa: TarefaTecnica, usuario, agendado_para=None) -> CodexExecucao:
    """Cria uma execução imediata ou agendada e dispara o worker em background."""

    status = CodexExecucao.STATUS_AGENDADA if agendado_para else CodexExecucao.STATUS_NA_FILA
    tipo = CodexExecucao.TIPO_AGENDADA if agendado_para else CodexExecucao.TIPO_MANUAL
    execucao = CodexExecucao.objects.create(
        tarefa=tarefa,
        criado_por=usuario,
        tipo=tipo,
        status=status,
        agendado_para=agendado_para,
    )
    disparar_worker_background()
    return execucao


def disparar_worker_background() -> None:
    """Sobe um processo desacoplado para manter a fila do Codex andando no servidor."""

    if "test" in sys.argv:
        return

    comando = [
        sys.executable,
        str(Path(settings.BASE_DIR) / "manage.py"),
        "processar_fila_codex",
    ]
    with open(os.devnull, "wb") as saida_nula:
        subprocess.Popen(
            comando,
            cwd=settings.BASE_DIR,
            stdout=saida_nula,
            stderr=saida_nula,
            stdin=saida_nula,
            start_new_session=True,
        )


def adquirir_lock_worker():
    """Impede múltiplos workers simultâneos usando um lockfile simples do sistema."""

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    arquivo = open(LOCK_PATH, "w", encoding="utf-8")
    try:
        fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        arquivo.close()
        return None

    arquivo.write(str(os.getpid()))
    arquivo.flush()
    return arquivo


def promover_execucoes_vencidas() -> int:
    """Converte execuções agendadas já vencidas para o status de fila pronta."""

    agora = timezone.now()
    return CodexExecucao.objects.filter(
        status=CodexExecucao.STATUS_AGENDADA,
        agendado_para__isnull=False,
        agendado_para__lte=agora,
    ).update(status=CodexExecucao.STATUS_NA_FILA, atualizado_em=agora)


def proxima_execucao_pendente() -> CodexExecucao | None:
    """Seleciona a próxima execução pronta para rodar respeitando a ordem da fila."""

    promover_execucoes_vencidas()
    return (
        CodexExecucao.objects.select_related("tarefa", "criado_por")
        .filter(status=CodexExecucao.STATUS_NA_FILA)
        .order_by("criado_em", "id")
        .first()
    )


def existe_execucao_pendente() -> bool:
    """Indica se ainda existe fila pendente ou agendada aguardando o worker."""

    return CodexExecucao.objects.filter(
        status__in=[CodexExecucao.STATUS_AGENDADA, CodexExecucao.STATUS_NA_FILA, CodexExecucao.STATUS_EM_EXECUCAO]
    ).exists()


def segundos_ate_proximo_agendamento() -> int | None:
    """Retorna quantos segundos faltam para o próximo item agendado ficar elegível."""

    proximo = (
        CodexExecucao.objects.filter(status=CodexExecucao.STATUS_AGENDADA, agendado_para__isnull=False)
        .order_by("agendado_para")
        .first()
    )
    if not proximo or not proximo.agendado_para:
        return None
    return max(int((proximo.agendado_para - timezone.now()).total_seconds()), 0)


def executar_fila_codex() -> int:
    """Processa a fila inteira enquanto houver itens prontos ou agendados próximos."""

    lock = adquirir_lock_worker()
    if lock is None:
        return 0

    processadas = 0
    try:
        while True:
            execucao = proxima_execucao_pendente()
            if execucao:
                processar_execucao(execucao.pk)
                processadas += 1
                continue

            espera = segundos_ate_proximo_agendamento()
            if espera is None:
                break
            time.sleep(min(max(espera, 1), 60))
    finally:
        lock.close()
        try:
            LOCK_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    return processadas


def processar_execucao(execucao_id: int) -> CodexExecucao:
    """Executa uma solicitação do Codex, aplica pós-passos e atualiza a tarefa vinculada."""

    with transaction.atomic():
        execucao = CodexExecucao.objects.select_related("tarefa").get(pk=execucao_id)
        if execucao.status != CodexExecucao.STATUS_NA_FILA:
            return execucao

        execucao.status = CodexExecucao.STATUS_EM_EXECUCAO
        execucao.iniciado_em = timezone.now()
        execucao.erro_detalhe = ""
        execucao.save(update_fields=["status", "iniciado_em", "erro_detalhe", "atualizado_em"])

    configuracao = get_codex_configuracao()
    prompt = montar_prompt_execucao(execucao, configuracao)
    schema = {
        "type": "object",
        "properties": {
            "titulo_final": {"type": "string"},
            "solucao_curta": {"type": "string"},
            "resumo_alteracoes": {"type": "string"},
            "testes_executados": {"type": "string"},
            "observacoes": {"type": "string"},
        },
        "required": ["titulo_final", "solucao_curta", "resumo_alteracoes", "testes_executados", "observacoes"],
        "additionalProperties": False,
    }

    try:
        with tempfile.TemporaryDirectory(prefix="todo-codex-") as diretorio_temp:
            schema_path = Path(diretorio_temp) / "schema.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

            ambiente = os.environ.copy()
            ambiente["CODEX_HOME"] = configuracao.codex_home
            ambiente["RUST_LOG"] = "error"

            comando = [
                configuracao.codex_path,
                "exec",
                "--sandbox",
                configuracao.sandbox,
                "--json",
                "--output-schema",
                str(schema_path),
                "-C",
                configuracao.workspace_path,
                prompt,
            ]
            if configuracao.habilitar_busca_web:
                comando.insert(2, "--search")

            processo = subprocess.run(
                comando,
                cwd=configuracao.workspace_path,
                capture_output=True,
                text=True,
                timeout=configuracao.timeout_minutos * 60,
                env=ambiente,
            )

        stdout = processo.stdout or ""
        stderr = processo.stderr or ""
        dados = interpretar_saida_codex(stdout, stderr)
        execucao.prompt_enviado = prompt
        execucao.thread_id = dados["thread_id"]
        execucao.resposta_final = dados["resposta_bruta"]
        execucao.log_completo = dados["log_completo"]
        execucao.log_resumido = dados["log_resumido"]
        execucao.input_tokens = dados["input_tokens"]
        execucao.cached_input_tokens = dados["cached_input_tokens"]
        execucao.output_tokens = dados["output_tokens"]
        execucao.reasoning_output_tokens = dados["reasoning_output_tokens"]
        execucao.total_tokens = dados["total_tokens"]

        if processo.returncode != 0:
            raise RuntimeError(f"Codex retornou código {processo.returncode}.")

        resposta = json.loads(dados["resposta_bruta"])
        saida_pos_execucao = rodar_pos_execucao(configuracao)

        tarefa = execucao.tarefa
        tarefa.titulo = (resposta["titulo_final"] or normalizar_titulo_tarefa(tarefa)).strip()
        tarefa.solucao = (resposta["solucao_curta"] or "").strip()
        tarefa.concluido_em = timezone.now()
        tarefa.save(update_fields=["titulo", "solucao", "concluido_em", "atualizado_em"])

        execucao.status = CodexExecucao.STATUS_CONCLUIDA
        execucao.finalizado_em = timezone.now()
        execucao.resumo_execucao = "\n".join(
            [
                resposta["resumo_alteracoes"].strip(),
                f"Testes/checks: {resposta['testes_executados'].strip()}",
                f"Observações: {resposta['observacoes'].strip()}",
            ]
        ).strip()
        execucao.titulo_gerado = tarefa.titulo
        execucao.solucao_gerada = tarefa.solucao
        execucao.saida_pos_execucao = saida_pos_execucao
        execucao.save()
        return execucao
    except subprocess.TimeoutExpired as exc:
        detalhe = f"Tempo limite excedido após {configuracao.timeout_minutos} minutos."
        return registrar_falha_execucao(execucao_id, detalhe, stdout=getattr(exc, "stdout", ""), stderr=getattr(exc, "stderr", ""))
    except Exception as exc:  # noqa: BLE001 - o worker precisa registrar qualquer erro para a fila.
        return registrar_falha_execucao(execucao_id, str(exc))


def interpretar_saida_codex(stdout: str, stderr: str) -> dict[str, object]:
    """Extrai thread, uso e resposta estruturada dos eventos JSONL do `codex exec`."""

    thread_id = ""
    resposta_bruta = ""
    log_resumido = []
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    reasoning_output_tokens = 0

    for linha in stdout.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            evento = json.loads(linha)
        except json.JSONDecodeError:
            if len(log_resumido) < 12:
                log_resumido.append(linha)
            continue

        tipo = evento.get("type")
        if tipo == "thread.started":
            thread_id = evento.get("thread_id", "") or thread_id
        elif tipo == "item.completed":
            item = evento.get("item") or {}
            if item.get("type") == "agent_message":
                resposta_bruta = item.get("text", "") or resposta_bruta
        elif tipo == "turn.completed":
            uso = evento.get("usage") or {}
            input_tokens = int(uso.get("input_tokens") or 0)
            cached_input_tokens = int(uso.get("cached_input_tokens") or 0)
            output_tokens = int(uso.get("output_tokens") or 0)
            reasoning_output_tokens = int(uso.get("reasoning_output_tokens") or 0)

        if len(log_resumido) < 12:
            log_resumido.append(linha[:400])

    if not resposta_bruta:
        raise ValueError("O Codex não retornou a resposta final estruturada.")

    total_tokens = input_tokens + output_tokens + reasoning_output_tokens
    return {
        "thread_id": thread_id,
        "resposta_bruta": resposta_bruta,
        "log_resumido": "\n".join(log_resumido),
        "log_completo": "\n".join([stdout.strip(), stderr.strip()]).strip(),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
    }


def rodar_pos_execucao(configuracao: CodexConfiguracao) -> str:
    """Executa o fechamento obrigatório do fluxo para manter a aplicação coerente após o Codex."""

    comandos = [
        [sys.executable, "manage.py", "makemigrations"],
        [sys.executable, "manage.py", "migrate"],
        [sys.executable, "manage.py", "check"],
        ["systemctl", "restart", configuracao.nome_servico],
    ]
    saidas = []
    for comando in comandos:
        processo = subprocess.run(
            comando,
            cwd=configuracao.workspace_path,
            capture_output=True,
            text=True,
            timeout=20 * 60,
        )
        trecho = f"$ {' '.join(comando)}\n{(processo.stdout or '').strip()}\n{(processo.stderr or '').strip()}".strip()
        saidas.append(trecho)
        if processo.returncode != 0:
            raise RuntimeError(f"Falha no pós-processamento: {' '.join(comando)}")
    return "\n\n".join(saidas).strip()


def registrar_falha_execucao(execucao_id: int, detalhe: str, stdout: str = "", stderr: str = "") -> CodexExecucao:
    """Concentra o caminho de erro para manter a fila coerente e auditável."""

    execucao = CodexExecucao.objects.get(pk=execucao_id)
    execucao.status = CodexExecucao.STATUS_ERRO
    execucao.finalizado_em = timezone.now()
    execucao.erro_detalhe = detalhe.strip()[:4000]
    execucao.log_completo = "\n".join(parte for parte in [execucao.log_completo, stdout or "", stderr or ""] if parte).strip()
    execucao.save()
    return execucao
