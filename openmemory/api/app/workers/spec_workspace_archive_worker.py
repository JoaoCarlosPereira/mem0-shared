"""Worker de auto-arquivamento de workspaces concluídos (Tarefa kanban-archive-lifecycle).

Um ``SpecWorkspace`` em ``concluido`` cujo ``completed_at`` ultrapassou a
janela configurável (padrão 30 dias) é movido para ``arquivado`` — mesma
transição do botão manual, via ``apply_status_change`` (grava
``archived_at``/``archived_by`` e espelha no PLANKA). O workspace nunca
desaparece: continua 100% visível via MCP/REST, só passa a aparecer recolhido
na home do Kanban (ADR pendente da feature).

Estrutura de classe (``run()``/``start()``/``stop()``, loop assíncrono) e
inicialização espelham ``spec_task_timeout_worker`` — iniciado em
``@app.on_event("startup")`` de ``main.py``, não como serviço Docker próprio.

Sem coluna de versão/OCC: a condição ``status == concluido`` na própria query
já é o guard de corrida — se duas réplicas processarem o mesmo workspace no
mesmo ciclo, a segunda apenas repete a mesma escrita (idempotente), sem
liberação dupla nem estado inconsistente.

Configuração sem deploy de código via variáveis de ambiente
(``SPEC_WORKSPACE_ARCHIVE_AFTER_DAYS``, ``SPEC_WORKSPACE_ARCHIVE_POLL_SECONDS``).
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import timedelta
from typing import Callable, Optional

from app.database import SessionLocal
from app.models import SpecWorkspace, SpecWorkspaceStatus, get_current_utc_time
from app.utils.workspace_lifecycle import apply_status_change

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE_AFTER_DAYS = 30.0
DEFAULT_POLL_SECONDS = 3600.0

# Ator gravado em ``SpecWorkspace.archived_by`` para transições automáticas —
# distingue de um e-mail/agente humano ao inspecionar o histórico.
AUTO_ARCHIVE_ACTOR = "system:auto-archive"


class SpecWorkspaceArchiveWorker:
    """Arquiva periodicamente workspaces ``concluido`` inativos além do limite.

    Args:
        archive_after_days: Janela (em dias) desde ``completed_at`` antes de arquivar.
        poll_seconds: Intervalo entre varreduras no loop de longa duração.
        session_factory: Fábrica de ``Session`` (injetável para testes).
        apply_change: Callable de transição (injetável); por padrão ``apply_status_change``.
    """

    def __init__(
        self,
        archive_after_days: float = DEFAULT_ARCHIVE_AFTER_DAYS,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        session_factory: Optional[Callable] = None,
        apply_change: Optional[Callable] = None,
    ):
        self._window = timedelta(days=max(0.0, float(archive_after_days)))
        self._poll = max(1.0, float(poll_seconds))
        self._session_factory = session_factory or SessionLocal
        self._apply_change = apply_change or apply_status_change

        self._task: Optional[asyncio.Task] = None
        self._stopped = asyncio.Event()

    # --------------------------------------------------------------------- #
    # Seleção de elegíveis + passe único (seam testável)
    # --------------------------------------------------------------------- #
    def eligible_workspaces(self, db, now=None):
        """Workspaces ``concluido`` com ``completed_at`` além da janela configurada."""
        now = now or get_current_utc_time()
        cutoff = now - self._window
        return (
            db.query(SpecWorkspace)
            .filter(
                SpecWorkspace.status == SpecWorkspaceStatus.concluido,
                SpecWorkspace.completed_at.isnot(None),
                SpecWorkspace.completed_at < cutoff,
            )
            .all()
        )

    def process_once(self) -> int:
        """Uma varredura: arquiva os workspaces elegíveis. Retorna quantos arquivou."""
        db = self._session_factory()
        try:
            archived = 0
            for workspace in self.eligible_workspaces(db):
                try:
                    self._apply_change(
                        db,
                        workspace,
                        SpecWorkspaceStatus.arquivado,
                        actor=AUTO_ARCHIVE_ACTOR,
                    )
                    archived += 1
                except Exception:  # noqa: BLE001 - uma falha não aborta o lote
                    logger.exception(
                        "spec-workspace-archive: falha ao arquivar workspace %s; continuando",
                        workspace.id,
                    )
            if archived:
                logger.info(
                    "spec-workspace-archive: %s workspace(s) arquivado(s) por inatividade pós-conclusão",
                    archived,
                )
            return archived
        except Exception:  # noqa: BLE001 - isolamento do worker de background
            logger.exception("spec-workspace-archive: passe falhou; continuando")
            return 0
        finally:
            db.close()

    # --------------------------------------------------------------------- #
    # Loop de longa duração + ciclo de vida (espelha spec_task_timeout_worker)
    # --------------------------------------------------------------------- #
    async def run(self) -> None:
        logger.info(
            "spec workspace archive worker started (window=%.1fd, poll=%.0fs)",
            self._window.total_seconds() / 86400,
            self._poll,
        )
        while not self._stopped.is_set():
            self.process_once()
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._poll)
            except asyncio.TimeoutError:
                pass
        logger.info("spec workspace archive worker stopped")

    def start(self) -> asyncio.Task:
        if self._task is None or self._task.done():
            self._stopped.clear()
            self._task = asyncio.create_task(self.run())
        return self._task

    async def stop(self) -> None:
        self._stopped.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def worker_from_env() -> SpecWorkspaceArchiveWorker:
    """Constrói o worker a partir de variáveis de ambiente (ajuste sem deploy)."""
    return SpecWorkspaceArchiveWorker(
        archive_after_days=_env_float(
            "SPEC_WORKSPACE_ARCHIVE_AFTER_DAYS", DEFAULT_ARCHIVE_AFTER_DAYS
        ),
        poll_seconds=_env_float(
            "SPEC_WORKSPACE_ARCHIVE_POLL_SECONDS", DEFAULT_POLL_SECONDS
        ),
    )


# Instância compartilhada usada pelo hook de startup da aplicação.
spec_workspace_archive_worker = worker_from_env()
