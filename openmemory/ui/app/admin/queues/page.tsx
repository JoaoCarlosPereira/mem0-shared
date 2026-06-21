"use client";

import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { format } from "date-fns";
import { AppDispatch, RootState } from "@/store/store";
import { useQueuesApi } from "@/hooks/useQueuesApi";
import { useAdminApi } from "@/hooks/useAdminApi";
import {
  setWriteQueueFilter,
  setGovernanceFilter,
} from "@/store/queuesSlice";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { QueueTable, QueueColumn } from "@/components/admin/QueueTable";
import { JobStatusBadge } from "@/components/admin/JobStatusBadge";
import {
  WriteQueueJob,
  GovernanceJob,
  WriteQueueStatus,
  GovernanceJobStatus,
} from "@/types/admin";

const ALL = "all";

function fmtDate(iso: string): string {
  try {
    return format(new Date(iso), "dd/MM/yyyy HH:mm:ss");
  } catch {
    return iso;
  }
}

function StatusCounters({
  queued,
  processing,
  done,
  failed,
}: {
  queued: number;
  processing: number;
  done: number;
  failed: number;
}) {
  return (
    <div className="mb-3 flex gap-4 text-sm text-zinc-400">
      <span>queued: {queued}</span>
      <span>processing: {processing}</span>
      <span>done: {done}</span>
      <span className={failed > 0 ? "text-red-400" : ""}>failed: {failed}</span>
    </div>
  );
}

export default function QueuesPage() {
  const dispatch = useDispatch<AppDispatch>();
  useAdminApi(); // popula contadores do overview no adminSlice
  const { fetchWriteQueue, fetchGovernanceJobs } = useQueuesApi();

  const writeQueue = useSelector((s: RootState) => s.queues.writeQueue);
  const governanceQueue = useSelector(
    (s: RootState) => s.queues.governanceQueue,
  );
  const writeFilter = useSelector((s: RootState) => s.queues.writeQueueFilter);
  const govFilter = useSelector((s: RootState) => s.queues.governanceFilter);
  const overview = useSelector((s: RootState) => s.admin.overview);

  // Re-fetch imediato quando os filtros mudam (fetchWriteQueue muda de
  // identidade junto com o filtro, pois é memoizado sobre seus campos).
  useEffect(() => {
    fetchWriteQueue();
  }, [fetchWriteQueue]);
  useEffect(() => {
    fetchGovernanceJobs();
  }, [fetchGovernanceJobs]);

  const writeColumns: QueueColumn<WriteQueueJob>[] = [
    { key: "project", header: "Projeto", render: (r) => r.project },
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
      render: (r) => fmtDate(r.created_at),
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
      render: (r) => fmtDate(r.created_at),
    },
  ];

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-zinc-100">Filas</h1>
      <Tabs defaultValue="write">
        <TabsList>
          <TabsTrigger value="write">Write Queue</TabsTrigger>
          <TabsTrigger value="governance">Governance Queue</TabsTrigger>
        </TabsList>

        <TabsContent value="write" className="mt-4">
          <StatusCounters
            queued={overview?.write_queue_queued ?? 0}
            processing={overview?.write_queue_processing ?? 0}
            done={0}
            failed={overview?.write_queue_failed ?? 0}
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
          </div>
          <QueueTable
            columns={writeColumns}
            data={writeQueue?.items ?? []}
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
            failed={overview?.governance_queue_failed ?? 0}
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
          </div>
          <QueueTable
            columns={govColumns}
            data={governanceQueue?.items ?? []}
            page={governanceQueue?.page ?? 1}
            pages={governanceQueue?.pages ?? 0}
            onPageChange={(p) => dispatch(setGovernanceFilter({ page: p }))}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
