"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { useDispatch, useSelector } from "react-redux";
import { formatDateTimeFull } from "@/lib/datetime";
import { AppDispatch, RootState } from "@/store/store";
import { useQueuesApi } from "@/hooks/useQueuesApi";
import { useAdminApi } from "@/hooks/useAdminApi";
import {
  setWriteQueueFilter,
  setGovernanceFilter,
  bumpQueueUiPrefs,
  selectUnacknowledgedFailedByKind,
} from "@/store/queuesSlice";
import {
  isHideCompleted,
  setHideCompleted,
  type QueueKind,
} from "@/lib/queue-ui-prefs";
import { useAcknowledgeQueueFailuresOnMount } from "@/hooks/useAcknowledgeQueueFailuresOnMount";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { QueueTable, QueueColumn } from "@/components/admin/QueueTable";
import { JobStatusBadge } from "@/components/admin/JobStatusBadge";
import { ActorLabel } from "@/components/shared/attribution-badge";
import { PageHeader } from "@/components/shared/PageHeader";
import { ListOrdered } from "lucide-react";
import {
  PaginatedWriteQueue,
  PaginatedGovernanceQueue,
  WriteQueueJob,
  GovernanceJob,
  WriteQueueStatus,
  GovernanceJobStatus,
} from "@/types/admin";

const ALL = "all";

function StatusCounters({
  queued,
  processing,
  done,
  skipped,
  failed,
}: {
  queued: number;
  processing: number;
  done: number;
  skipped: number;
  failed: number;
}) {
  return (
    <div className="mb-3 flex flex-wrap gap-4 text-sm text-zinc-400">
      <span>na fila: {queued}</span>
      <span>processando: {processing}</span>
      <span>concluído: {done}</span>
      <span className={skipped > 0 ? "text-amber-400" : ""}>
        ignorado: {skipped}
      </span>
      <span className={failed > 0 ? "text-red-400" : ""}>falhou: {failed}</span>
    </div>
  );
}

export default function QueuesPage() {
  const dispatch = useDispatch<AppDispatch>();
  const { fetchAdminOverview } = useAdminApi(); // popula contadores do overview no adminSlice
  const { fetchWriteQueue, fetchGovernanceJobs, retryFailedWriteJobs } =
    useQueuesApi();
  const [retrying, setRetrying] = useState(false);

  const writeQueue = useSelector((s: RootState) => s.queues.writeQueue);
  const governanceQueue = useSelector(
    (s: RootState) => s.queues.governanceQueue,
  );
  const writeFilter = useSelector((s: RootState) => s.queues.writeQueueFilter);
  const govFilter = useSelector((s: RootState) => s.queues.governanceFilter);
  const overview = useSelector((s: RootState) => s.admin.overview);
  const uiPrefsVersion = useSelector((s: RootState) => s.queues.uiPrefsVersion);
  const unacknowledged = useSelector(selectUnacknowledgedFailedByKind);
  useAcknowledgeQueueFailuresOnMount();

  const hideWriteCompleted = useMemo(
    () => isHideCompleted("write"),
    [uiPrefsVersion],
  );
  const hideGovCompleted = useMemo(
    () => isHideCompleted("governance"),
    [uiPrefsVersion],
  );

  const visibleWriteItems = useMemo(() => {
    const items = writeQueue?.items ?? [];
    return hideWriteCompleted
      ? items.filter((j) => j.status !== "done")
      : items;
  }, [writeQueue?.items, hideWriteCompleted]);

  const visibleGovItems = useMemo(() => {
    const items = governanceQueue?.items ?? [];
    return hideGovCompleted ? items.filter((j) => j.status !== "done") : items;
  }, [governanceQueue?.items, hideGovCompleted]);

  const handleHideCompleted = useCallback(
    (kind: QueueKind) => {
      setHideCompleted(kind, true);
      dispatch(bumpQueueUiPrefs());
      toast.success("Concluídos ocultados da visualização (somente UI).");
    },
    [dispatch],
  );

  const handleShowCompleted = useCallback(
    (kind: QueueKind) => {
      setHideCompleted(kind, false);
      dispatch(bumpQueueUiPrefs());
    },
    [dispatch],
  );

  // Re-fetch imediato quando os filtros mudam (fetchWriteQueue muda de
  // identidade junto com o filtro, pois é memoizado sobre seus campos).
  useEffect(() => {
    fetchWriteQueue();
  }, [fetchWriteQueue]);
  useEffect(() => {
    fetchGovernanceJobs();
  }, [fetchGovernanceJobs]);

  const failedCount = overview?.write_queue_failed ?? writeQueue?.failed_count ?? 0;

  const handleRetryFailed = useCallback(async () => {
    setRetrying(true);
    try {
      const result = await retryFailedWriteJobs(writeFilter.project);
      if (result.requeued === 0) {
        toast.info("Nenhum job falhado para reprocessar.");
      } else {
        toast.success(
          `${result.requeued} job(s) reenfileirado(s) para reprocessamento.`,
        );
      }
      await Promise.all([fetchWriteQueue(), fetchAdminOverview()]);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Falha ao reprocessar jobs";
      toast.error(message);
    } finally {
      setRetrying(false);
    }
  }, [
    retryFailedWriteJobs,
    writeFilter.project,
    fetchWriteQueue,
    fetchAdminOverview,
  ]);

  const writeColumns: QueueColumn<WriteQueueJob>[] = [
    { key: "project", header: "Projeto", render: (r) => r.project },
    {
      key: "hostname",
      header: "Usuário",
      render: (r) => (
        <ActorLabel
          hostname={r.hostname}
          clientName={r.client_name}
          displayName={r.user_display_name}
          avatarUrl={r.user_avatar_url}
        />
      ),
    },
    {
      key: "text",
      header: "Texto",
      render: (r) => (
        <span className="block max-w-xs truncate" title={r.text_preview}>
          {r.text_preview}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <JobStatusBadge status={r.status} />,
    },
    { key: "attempts", header: "Tentativas", render: (r) => r.attempts },
    {
      key: "error",
      header: "Detalhe",
      render: (r) =>
        r.error ? (
          <span
            className={`block max-w-xs truncate ${
              r.status === "failed"
                ? "text-red-400"
                : r.status === "skipped"
                  ? "text-amber-400"
                  : "text-zinc-400"
            }`}
            title={r.error}
          >
            {r.error}
          </span>
        ) : (
          <span className="text-zinc-600">—</span>
        ),
    },
    {
      key: "created_at",
      header: "Criado em",
      render: (r) => formatDateTimeFull(r.created_at),
    },
  ];

  const govColumns: QueueColumn<GovernanceJob>[] = [
    { key: "job_type", header: "Tipo", render: (r) => r.job_type },
    {
      key: "project",
      header: "Projeto",
      render: (r) => r.project ?? <span className="text-zinc-600">global</span>,
    },
    {
      key: "status",
      header: "Status",
      render: (r) => <JobStatusBadge status={r.status} />,
    },
    { key: "attempts", header: "Tentativas", render: (r) => r.attempts },
    {
      key: "error",
      header: "Erro",
      render: (r) =>
        r.error ? (
          <span className="block max-w-xs truncate text-red-400" title={r.error}>
            {r.error}
          </span>
        ) : (
          <span className="text-zinc-600">—</span>
        ),
    },
    {
      key: "created_at",
      header: "Criado em",
      render: (r) => formatDateTimeFull(r.created_at),
    },
  ];

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={ListOrdered}
        title="Filas"
        description="Monitoramento das filas de escrita e governança"
      />
      <Tabs defaultValue="write">
        <TabsList>
          <TabsTrigger value="write">Fila de Escrita</TabsTrigger>
          <TabsTrigger value="governance">Fila de Governança</TabsTrigger>
        </TabsList>

        <TabsContent value="write" className="mt-4">
          <StatusCounters
            queued={overview?.write_queue_queued ?? 0}
            processing={overview?.write_queue_processing ?? 0}
            done={overview?.write_queue_done ?? 0}
            skipped={overview?.write_queue_skipped ?? 0}
            failed={unacknowledged.write}
          />
          <div className="mb-3 flex gap-2">
            <Select
              value={writeFilter.status ?? ALL}
              onValueChange={(v) =>
                dispatch(
                  setWriteQueueFilter({
                    status:
                      v === ALL ? undefined : (v as WriteQueueStatus),
                    page: 1,
                  }),
                )
              }
            >
              <SelectTrigger className="w-40" aria-label="Filtrar por status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Todos status</SelectItem>
                <SelectItem value="queued">queued</SelectItem>
                <SelectItem value="processing">processing</SelectItem>
                <SelectItem value="done">done</SelectItem>
                <SelectItem value="skipped">skipped</SelectItem>
                <SelectItem value="failed">failed</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Filtrar por projeto"
              className="w-56"
              defaultValue={writeFilter.project ?? ""}
              onBlur={(e) =>
                dispatch(
                  setWriteQueueFilter({
                    project: e.target.value || undefined,
                    page: 1,
                  }),
                )
              }
            />
            <Button
              type="button"
              variant="outline"
              disabled={failedCount === 0 || retrying}
              onClick={handleRetryFailed}
            >
              {retrying ? "Reprocessando…" : "Reprocessar Falhas"}
            </Button>
            {hideWriteCompleted ? (
              <Button
                type="button"
                variant="ghost"
                onClick={() => handleShowCompleted("write")}
              >
                Mostrar concluídos
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                onClick={() => handleHideCompleted("write")}
              >
                Ocultar concluídos
              </Button>
            )}
          </div>
          <QueueTable
            columns={writeColumns}
            data={visibleWriteItems}
            page={writeQueue?.page ?? 1}
            pages={writeQueue?.pages ?? 0}
            onPageChange={(p) => dispatch(setWriteQueueFilter({ page: p }))}
          />
        </TabsContent>

        <TabsContent value="governance" className="mt-4">
          <StatusCounters
            queued={overview?.governance_queue_queued ?? 0}
            processing={overview?.governance_queue_processing ?? 0}
            done={0}
            skipped={0}
            failed={unacknowledged.governance}
          />
          <div className="mb-3 flex gap-2">
            <Select
              value={govFilter.status ?? ALL}
              onValueChange={(v) =>
                dispatch(
                  setGovernanceFilter({
                    status:
                      v === ALL ? undefined : (v as GovernanceJobStatus),
                    page: 1,
                  }),
                )
              }
            >
              <SelectTrigger className="w-40" aria-label="Filtrar governance por status">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>Todos status</SelectItem>
                <SelectItem value="queued">queued</SelectItem>
                <SelectItem value="processing">processing</SelectItem>
                <SelectItem value="done">done</SelectItem>
                <SelectItem value="failed">failed</SelectItem>
              </SelectContent>
            </Select>
            <Input
              placeholder="Filtrar por projeto"
              className="w-56"
              defaultValue={govFilter.project ?? ""}
              onBlur={(e) =>
                dispatch(
                  setGovernanceFilter({
                    project: e.target.value || undefined,
                    page: 1,
                  }),
                )
              }
            />
            {hideGovCompleted ? (
              <Button
                type="button"
                variant="ghost"
                onClick={() => handleShowCompleted("governance")}
              >
                Mostrar concluídos
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                onClick={() => handleHideCompleted("governance")}
              >
                Ocultar concluídos
              </Button>
            )}
          </div>
          <QueueTable
            columns={govColumns}
            data={visibleGovItems}
            page={governanceQueue?.page ?? 1}
            pages={governanceQueue?.pages ?? 0}
            onPageChange={(p) => dispatch(setGovernanceFilter({ page: p }))}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
