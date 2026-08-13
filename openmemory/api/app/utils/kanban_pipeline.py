"""Orientação do pipeline Kanban Shared para respostas MCP.

Colunas de card: ``tasks`` → ``em_andamento`` → ``revisao_codigo`` →
``fase_teste`` → ``concluido``. Cada resposta de claim/update inclui o que a
coluna atual significa e o que o agente DEVE fazer antes da próxima transição.
"""

from __future__ import annotations

from typing import Any

from app.models import TaskCardStatus

_kanban_prompts_cache: dict | None = None


def _get_kanban_prompts_cache() -> dict:
    """Lazy-import cache from mcp_server to avoid circular imports."""
    global _kanban_prompts_cache
    if _kanban_prompts_cache is None:
        from app.mcp_server import _kanban_prompts_cache as cache
        _kanban_prompts_cache = cache
    return _kanban_prompts_cache

# Ordem avançada (sem ``tasks`` — entrada via claim_task).
FORWARD_PIPELINE: tuple[TaskCardStatus, ...] = (
    TaskCardStatus.em_andamento,
    TaskCardStatus.revisao_codigo,
    TaskCardStatus.fase_teste,
    TaskCardStatus.concluido,
)

COLUMN_GUIDE: dict[str, dict[str, str | None]] = {
    TaskCardStatus.tasks.value: {
        "label": "Backlog (Tasks)",
        "means": (
            "Card aguardando execução. Ainda não há responsável; não edite código."
        ),
        "do_now": (
            "Quando for implementar: chame claim_task(task_id). "
            "Isso move o card para em_andamento e atribui você como assignee."
        ),
        "next_column": TaskCardStatus.em_andamento.value,
        "next_action": "claim_task",
    },
    TaskCardStatus.em_andamento.value: {
        "label": "Em andamento",
        "means": (
            "Implementação em curso. Você é o assignee; escopo = descrição do card."
        ),
        "do_now": (
            "Implemente o código no escopo do card. Em bloqueio: update_task_status "
            "com o mesmo status, is_blocked=true, block_reason e add_spec_comment. "
            "Quando a implementação estiver pronta para review (NÃO concluída): "
            "update_task_status(..., 'revisao_codigo', expected_version=...). "
            "PROIBIDO ir para fase_teste ou concluido a partir daqui."
        ),
        "next_column": TaskCardStatus.revisao_codigo.value,
        "next_action": "update_task_status",
    },
    TaskCardStatus.revisao_codigo.value: {
        "label": "Revisão de código",
        "means": (
            "Diff pronto para review (self-review ou peer). Ainda não é fase de testes "
            "nem conclusão."
        ),
        "do_now": (
            "Revise o diff; anote achados com add_spec_comment. Se precisar corrigir: "
            "update_task_status(..., 'em_andamento'). Se a review estiver ok: "
            "update_task_status(..., 'fase_teste', expected_version=...). "
            "PROIBIDO ir para concluido a partir daqui."
        ),
        "next_column": TaskCardStatus.fase_teste.value,
        "next_action": "update_task_status",
    },
    TaskCardStatus.fase_teste.value: {
        "label": "Fase de teste",
        "means": (
            "Validação com evidência fresca (testes/lint/build). Única coluna de onde "
            "se pode ir para concluido."
        ),
        "do_now": (
            "Execute cy-final-verify / comandos de teste do card NESTA coluna. "
            "Comente evidência (comando + exit code) via add_spec_comment se útil. "
            "Se REPROVADO: is_blocked=true ou volte a em_andamento/revisao_codigo. "
            "Só com veredito APROVADO: update_task_status(..., 'concluido', ...)."
        ),
        "next_column": TaskCardStatus.concluido.value,
        "next_action": "update_task_status",
    },
    TaskCardStatus.concluido.value: {
        "label": "Concluído",
        "means": (
            "Card finalizado após review e testes. Não há próxima coluna no pipeline."
        ),
        "do_now": (
            "Não altere mais o status salvo correção excepcional (voltar a "
            "em_andamento via update_task_status). Escolha outra task no backlog "
            "com claim_task. Se a feature inteira acabou: "
            "update_spec_workspace_status(..., 'concluido')."
        ),
        "next_column": None,
        "next_action": None,
    },
}

_PIPELINE_RULE = (
    "Execute TODAS as etapas na ordem. Após cada claim_task/update_task_status, "
    "leia kanban.do_now e cumpra essa coluna antes de avançar. Nunca pule "
    "revisao_codigo ou fase_teste."
)


def guide_for(status: str | TaskCardStatus) -> dict[str, Any]:
    """Retorna bloco de orientação para a coluna atual."""
    key = status.value if isinstance(status, TaskCardStatus) else str(status)
    base = COLUMN_GUIDE.get(key)
    pipeline = [
        TaskCardStatus.tasks.value,
        *[s.value for s in FORWARD_PIPELINE],
    ]
    if not base:
        return {
            "column": key,
            "label": key,
            "means": "Coluna desconhecida.",
            "do_now": "Consulte o quadro e o pipeline obrigatório.",
            "next_column": None,
            "next_action": None,
            "pipeline": pipeline,
            "pipeline_rule": _PIPELINE_RULE,
        }
    return {
        "column": key,
        "label": base["label"],
        "means": base["means"],
        "do_now": base["do_now"],
        "next_column": base["next_column"],
        "next_action": base["next_action"],
        "pipeline": pipeline,
        "pipeline_rule": _PIPELINE_RULE,
    }


def enrich_status_payload(
    payload: dict[str, Any],
    status: str,
    db: Any | None = None,
) -> dict[str, Any]:
    """Anexa ``kanban`` (orientação da coluna atual) ao JSON de resposta MCP."""
    out = dict(payload)
    kanban_info = guide_for(status)

    if db is not None:
        from app.mcp_server import (
            _kanban_prompts_cache_expired,
            _load_kanban_prompts_cache,
        )

        if _kanban_prompts_cache_expired():
            _load_kanban_prompts_cache(db)

    # Injeta column_prompt do cache (se disponível e habilitado)
    cache = _get_kanban_prompts_cache()
    prompt_data = cache.get(status) if cache else None
    if prompt_data and prompt_data.get("is_enabled") and prompt_data.get("prompt"):
        kanban_info["column_prompt"] = prompt_data["prompt"]
    else:
        kanban_info["column_prompt"] = None

    out["kanban"] = kanban_info
    return out


class KanbanSkipError(ValueError):
    """Avanço que pula etapa do pipeline."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def assert_no_forward_skip(
    old_status: TaskCardStatus,
    new_status: TaskCardStatus,
) -> None:
    """Rejeita avanços que pulam colunas (ex.: em_andamento→concluido).

    Retrocesso e permanecer na mesma coluna (bloqueio) são permitidos.
    Entrada/saída de ``tasks`` continua nas policies claim/release.
    """
    if old_status == new_status:
        return
    if old_status == TaskCardStatus.tasks or new_status == TaskCardStatus.tasks:
        return
    try:
        old_i = FORWARD_PIPELINE.index(old_status)
        new_i = FORWARD_PIPELINE.index(new_status)
    except ValueError:
        return
    if new_i > old_i + 1:
        nxt = FORWARD_PIPELINE[old_i + 1].value
        raise KanbanSkipError(
            "skip_pipeline",
            (
                f"Não pode ir de {old_status.value} para {new_status.value}. "
                f"Avance uma coluna por vez: {old_status.value} → {nxt}. "
                f"Faça o trabalho da coluna atual (veja kanban.do_now) antes de avançar."
            ),
        )
