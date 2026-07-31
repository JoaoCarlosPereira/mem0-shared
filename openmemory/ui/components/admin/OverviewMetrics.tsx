"use client";

import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { selectUnacknowledgedFailedByKind } from "@/store/queuesSlice";
import { StatCard } from "@/components/admin/StatCard";
import { Skeleton } from "@/components/ui/skeleton";
import { FolderKanban, Layers, Clock3, PenLine, Scale } from "lucide-react";

/**
 * Status do write-worker: heartbeat da API tem prioridade; senão heurística
 * por jobs em processing/queued.
 */
export function workerHint(
  processing: number,
  queued: number,
  opts?: { stalled?: boolean; alive?: boolean },
): string {
  if (opts?.stalled) return "Worker parado (sem heartbeat) — reprocessar falhas";
  if (opts?.alive === false) return "Worker sem sinal";
  if (processing > 0) return "Worker ativo (processando)";
  if (queued > 0) return "Aguardando — jobs na fila";
  return "Ocioso";
}

/** Contagem de falhas para alerta: IDs do polling quando disponíveis; senão overview da API. */
export function failedAlertCount(
  apiCount: number,
  polledIds: string[],
  unacknowledged: number,
): number {
  if (polledIds.length > 0) return unacknowledged;
  return apiCount;
}

interface OverviewMetricsProps {
  /** Exibe botão de retry quando há erro e overview ainda não carregou. */
  onRetry?: () => void;
  className?: string;
}

export function OverviewMetrics({ onRetry, className }: OverviewMetricsProps) {
  const overview = useSelector((state: RootState) => state.admin.overview);
  const error = useSelector((state: RootState) => state.admin.error);
  const loading = useSelector((state: RootState) => state.admin.loading);
  const failedWriteJobIds = useSelector(
    (state: RootState) => state.queues.failedWriteJobIds,
  );
  const failedGovernanceJobIds = useSelector(
    (state: RootState) => state.queues.failedGovernanceJobIds,
  );
  const unacknowledged = useSelector(selectUnacknowledgedFailedByKind);

  if (error && !overview) {
    return (
      <div className={className}>
        <p className="mb-3 text-sm text-red-400">{error}</p>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 hover:bg-zinc-700"
          >
            Tentar novamente
          </button>
        ) : null}
      </div>
    );
  }

  if (!overview) {
    return (
      <div className={className}>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
          ))}
        </div>
        {loading ? (
          <p className="mt-3 text-xs text-zinc-500">Carregando métricas…</p>
        ) : null}
      </div>
    );
  }

  const writeDepth = overview.write_queue_queued + overview.write_queue_processing;
  const govDepth =
    overview.governance_queue_queued + overview.governance_queue_processing;

  const writeFailed = failedAlertCount(
    overview.write_queue_failed,
    failedWriteJobIds,
    unacknowledged.write,
  );
  const govFailed = failedAlertCount(
    overview.governance_queue_failed,
    failedGovernanceJobIds,
    unacknowledged.governance,
  );

  const writeWorkerOpts = {
    stalled: overview.write_worker_stalled === true,
    alive: overview.write_worker_alive !== false,
  };
  const writeAlert = writeFailed > 0 || writeWorkerOpts.stalled;

  return (
    <div
      id="metrics-panel"
      className={className ?? "grid grid-cols-2 gap-4 md:grid-cols-3"}
    >
      <StatCard
        title="Total de Projetos"
        value={overview.total_projects}
        icon={FolderKanban}
        accent="violet"
      />
      <StatCard
        title="Total de Memórias"
        value={overview.total_memories}
        icon={Layers}
        accent="blue"
      />
      <StatCard
        title="Memórias (últimas 24h)"
        value={overview.memories_last_24h}
        icon={Clock3}
        accent="cyan"
      />
      <StatCard
        title="Fila de Escrita"
        value={writeDepth}
        icon={PenLine}
        accent="emerald"
        alert={writeAlert}
        hint={
          writeFailed > 0
            ? `${writeFailed} com falha · ${workerHint(overview.write_queue_processing, overview.write_queue_queued, writeWorkerOpts)}`
            : workerHint(
                overview.write_queue_processing,
                overview.write_queue_queued,
                writeWorkerOpts,
              )
        }
      />
      <StatCard
        title="Fila de Governança"
        value={govDepth}
        icon={Scale}
        accent="amber"
        alert={govFailed > 0}
        hint={
          govFailed > 0
            ? `${govFailed} com falha · ${workerHint(overview.governance_queue_processing, overview.governance_queue_queued)}`
            : workerHint(
                overview.governance_queue_processing,
                overview.governance_queue_queued,
              )
        }
      />
    </div>
  );
}

export default OverviewMetrics;
