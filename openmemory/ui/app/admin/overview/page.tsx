"use client";

import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useAdminApi } from "@/hooks/useAdminApi";
import { useAcknowledgeQueueFailuresOnMount } from "@/hooks/useAcknowledgeQueueFailuresOnMount";
import { selectUnacknowledgedFailedByKind } from "@/store/queuesSlice";
import { StatCard } from "@/components/admin/StatCard";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/PageHeader";
import { LayoutDashboard } from "lucide-react";

/**
 * Heurística de "worker ativo" no MVP: o overview não expõe heartbeat do worker.
 * Inferimos atividade pela presença de jobs em `processing`. Sem jobs em
 * processing o worker é reportado como "aguardando" (não necessariamente parado);
 * jobs presos em `processing` por muito tempo são o sinal real de worker parado,
 * documentado nas Perguntas em Aberto do PRD.
 */
function workerHint(processing: number, queued: number): string {
  if (processing > 0) return "Worker ativo (processando)";
  if (queued > 0) return "Aguardando — jobs na fila";
  return "Ocioso";
}

/** Contagem de falhas para alerta: IDs do polling quando disponíveis; senão overview da API. */
function failedAlertCount(
  apiCount: number,
  polledIds: string[],
  unacknowledged: number,
): number {
  if (polledIds.length > 0) return unacknowledged;
  return apiCount;
}

export default function OverviewPage() {
  const { fetchAdminOverview } = useAdminApi();
  useAcknowledgeQueueFailuresOnMount();
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
      <div>
        <PageHeader className="mb-4" icon={LayoutDashboard} title="Visão Geral" />
        <p className="mb-3 text-sm text-red-400">{error}</p>
        <button
          type="button"
          onClick={() => void fetchAdminOverview()}
          className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 hover:bg-zinc-700"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (!overview) {
    return (
      <div>
        <PageHeader className="mb-4" icon={LayoutDashboard} title="Visão Geral" />
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

  return (
    <div>
      <PageHeader className="mb-4" icon={LayoutDashboard} title="Visão Geral" />
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCard title="Total de Projetos" value={overview.total_projects} />
        <StatCard title="Total de Memórias" value={overview.total_memories} />
        <StatCard
          title="Memórias (últimas 24h)"
          value={overview.memories_last_24h}
        />
        <StatCard
          title="Fila de Escrita"
          value={writeDepth}
          alert={writeFailed > 0}
          hint={
            writeFailed > 0
              ? `${writeFailed} com falha · ${workerHint(overview.write_queue_processing, overview.write_queue_queued)}`
              : workerHint(
                  overview.write_queue_processing,
                  overview.write_queue_queued,
                )
          }
        />
        <StatCard
          title="Fila de Governança"
          value={govDepth}
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
    </div>
  );
}
