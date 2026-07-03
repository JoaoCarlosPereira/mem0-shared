"""Persistência assíncrona de métricas de consumo de tokens (task_02).

O caminho quente (chamada LLM/embedding) só enfileira um ``TokenUsageRecord``
em uma ``queue.Queue`` (custo ~µs, meta < 1ms do PRD); uma thread daemon de
background drena a fila em lotes e grava ``TokenUsageLog`` no banco em uma
única transação por lote.

Degradação graciosa (fail-open): qualquer falha — fila, sessão, commit — é
logada e engolida. Perder um registro de métrica nunca pode derrubar a
operação de memória que o originou.
"""

import logging
import queue
import threading
import time
from typing import Callable, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Quantos registros gravar por transação, no máximo.
DEFAULT_MAX_BATCH = 200
# Quanto tempo (s) a thread de flush espera por um novo item antes de idle.
DEFAULT_POLL_TIMEOUT = 0.5


class TokenUsageRecord(BaseModel):
    """Dados de uma chamada LLM/embedding a persistir em ``token_usage_logs``."""

    project: str = "unknown"
    agent: str = "unknown"
    user_id: str = "unknown"
    operation_type: str = "unknown"
    model: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    duration_ms: Optional[int] = None
    success: bool = True
    error: Optional[str] = None
    trace_id: Optional[str] = None


def _default_session_factory():
    from app.database import SessionLocal

    return SessionLocal()


class TokenUsageService:
    """Gravador não-bloqueante de registros de uso de tokens.

    Args:
        session_factory: Zero-arg callable que retorna uma Session SQLAlchemy.
            Injetável para testes; por padrão usa ``app.database.SessionLocal``.
        max_batch: Máximo de registros por transação de flush.
        poll_timeout: Segundos que a thread de flush aguarda por item novo.
    """

    def __init__(
        self,
        session_factory: Optional[Callable] = None,
        max_batch: int = DEFAULT_MAX_BATCH,
        poll_timeout: float = DEFAULT_POLL_TIMEOUT,
    ):
        self._session_factory = session_factory or _default_session_factory
        self._max_batch = max(1, int(max_batch))
        self._poll_timeout = poll_timeout
        self._queue: "queue.Queue[TokenUsageRecord]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._thread_lock = threading.Lock()
        self._stopped = threading.Event()

    # ------------------------------------------------------------------ #
    # Caminho quente
    # ------------------------------------------------------------------ #
    def record_usage(self, record: TokenUsageRecord) -> None:
        """Enfileira um registro para gravação em background. Nunca levanta."""
        try:
            self._queue.put_nowait(record)
            self._ensure_writer()
        except Exception:  # noqa: BLE001 - métricas nunca quebram o caller
            logger.exception("token usage enqueue failed; record dropped")

    def record_many(self, records: List[TokenUsageRecord]) -> None:
        """Enfileira vários registros (gravados em lote). Nunca levanta."""
        for record in records:
            self.record_usage(record)

    # ------------------------------------------------------------------ #
    # Escrita em background
    # ------------------------------------------------------------------ #
    def _ensure_writer(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._thread_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stopped.clear()
            self._thread = threading.Thread(
                target=self._writer_loop,
                name="token-usage-writer",
                daemon=True,
            )
            self._thread.start()

    def _writer_loop(self) -> None:
        while not self._stopped.is_set():
            batch = self._drain_batch()
            if not batch:
                continue
            try:
                self._write_batch(batch)
            except Exception:  # noqa: BLE001 - loop nunca morre
                logger.exception(
                    "token usage flush failed; %s records dropped", len(batch)
                )
            finally:
                for _ in batch:
                    self._queue.task_done()

    def _drain_batch(self) -> List[TokenUsageRecord]:
        """Bloqueia até chegar um item (ou timeout) e drena até ``max_batch``."""
        batch: List[TokenUsageRecord] = []
        try:
            batch.append(self._queue.get(timeout=self._poll_timeout))
        except queue.Empty:
            return batch
        while len(batch) < self._max_batch:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _write_batch(self, batch: List[TokenUsageRecord]) -> None:
        from app.models import TokenUsageLog

        db = self._session_factory()
        try:
            db.add_all(TokenUsageLog(**record.model_dump()) for record in batch)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------ #
    # Sincronização (testes / shutdown)
    # ------------------------------------------------------------------ #
    def flush(self, timeout: float = 5.0) -> bool:
        """Aguarda a fila esvaziar. Retorna ``False`` se o timeout expirar."""
        self._ensure_writer()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._queue.unfinished_tasks == 0:
                return True
            time.sleep(0.01)
        return self._queue.unfinished_tasks == 0

    def stop(self, timeout: float = 5.0) -> None:
        """Drena a fila e encerra a thread de flush (uso em shutdown/testes)."""
        self.flush(timeout)
        self._stopped.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout)


# Singleton compartilhado pelos pontos de instrumentação (wrapper, worker, MCP).
token_usage_service = TokenUsageService()
