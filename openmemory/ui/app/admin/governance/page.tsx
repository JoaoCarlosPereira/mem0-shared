"use client";

import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { useSelector } from "react-redux";
import { format } from "date-fns";
import { RootState } from "@/store/store";
import { useQueuesApi } from "@/hooks/useQueuesApi";
import { useAdminApi } from "@/hooks/useAdminApi";
import { QueueTable, QueueColumn } from "@/components/admin/QueueTable";
import { JobStatusBadge } from "@/components/admin/JobStatusBadge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { GovernanceJob, ProjectSize } from "@/types/admin";

const URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

const JOB_TYPES: { type: string; label: string; destructive?: boolean }[] = [
  { type: "dedup", label: "Dedup" },
  { type: "ttl_prune", label: "TTL Prune" },
  { type: "consolidate", label: "Consolidate" },
  { type: "purge", label: "Purge", destructive: true },
];

function fmtDate(iso: string): string {
  try {
    return format(new Date(iso), "dd/MM/yyyy HH:mm:ss");
  } catch {
    return iso;
  }
}

export default function GovernancePage() {
  const { fetchGovernanceJobs } = useQueuesApi();
  const { fetchProjectSizes } = useAdminApi({ poll: false });
  const governanceQueue = useSelector(
    (s: RootState) => s.queues.governanceQueue,
  );

  const [projects, setProjects] = useState<ProjectSize[]>([]);
  const [policies, setPolicies] = useState<Record<string, unknown> | null>(
    null,
  );
  const [dialogJob, setDialogJob] = useState<{
    type: string;
    label: string;
    destructive?: boolean;
  } | null>(null);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [dispatching, setDispatching] = useState(false);

  useEffect(() => {
    fetchProjectSizes()
      .then((res) => setProjects(res.projects))
      .catch(() => {});
    axios
      .get(`${URL}/admin/governance/policies`)
      .then((res) => setPolicies(res.data))
      .catch(() => {});
  }, [fetchProjectSizes]);

  const handleDispatch = useCallback(async () => {
    if (!dialogJob) return;
    setDispatching(true);
    try {
      await axios.post(`${URL}/admin/governance/jobs/${dialogJob.type}`, {
        project: selectedProject || null,
      });
      toast.success(`Job ${dialogJob.label} enfileirado`);
      setDialogJob(null);
      setSelectedProject("");
      await fetchGovernanceJobs();
    } catch {
      toast.error("Falha ao disparar o job");
    } finally {
      setDispatching(false);
    }
  }, [dialogJob, selectedProject, fetchGovernanceJobs]);

  const columns: QueueColumn<GovernanceJob>[] = [
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
    {
      key: "created_at",
      header: "Criado em",
      render: (r) => fmtDate(r.created_at),
    },
  ];

  return (
    <div>
      <h1 className="mb-4 text-xl font-semibold text-zinc-100">Governança</h1>

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-medium text-zinc-400">
          Disparo manual
        </h2>
        <div className="flex flex-wrap gap-2">
          {JOB_TYPES.map((jt) => (
            <Button
              key={jt.type}
              variant={jt.destructive ? "destructive" : "outline"}
              size="sm"
              onClick={() => setDialogJob(jt)}
            >
              {jt.label}
            </Button>
          ))}
        </div>
      </section>

      <section className="mb-6">
        <h2 className="mb-2 text-sm font-medium text-zinc-400">
          Jobs de governança
        </h2>
        <QueueTable
          columns={columns}
          data={governanceQueue?.items ?? []}
          page={governanceQueue?.page ?? 1}
          pages={governanceQueue?.pages ?? 0}
          onPageChange={() => {}}
          emptyMessage="Nenhum job de governança"
        />
      </section>

      <section>
        <h2 className="mb-2 text-sm font-medium text-zinc-400">
          Políticas ativas (somente leitura)
        </h2>
        <pre className="max-h-64 overflow-auto rounded-md border border-zinc-800 bg-zinc-900 p-3 text-xs text-zinc-300">
          {policies ? JSON.stringify(policies, null, 2) : "Carregando…"}
        </pre>
      </section>

      <Dialog
        open={dialogJob !== null}
        onOpenChange={(o) => {
          if (!o) {
            setDialogJob(null);
            setSelectedProject("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Disparar {dialogJob?.label}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            {dialogJob?.destructive && (
              <p className="text-sm font-semibold text-red-500">
                Esta ação é DESTRUTIVA e não pode ser desfeita.
              </p>
            )}
            <label className="block text-sm text-zinc-400">
              Projeto-alvo
            </label>
            <Select
              value={selectedProject || "__all__"}
              onValueChange={(v) =>
                setSelectedProject(v === "__all__" ? "" : v)
              }
            >
              <SelectTrigger aria-label="Selecionar projeto">
                <SelectValue placeholder="Todos os projetos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Todos os projetos</SelectItem>
                {projects.map((p) => (
                  <SelectItem key={p.name} value={p.name}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDialogJob(null);
                setSelectedProject("");
              }}
            >
              Cancelar
            </Button>
            <Button
              variant={dialogJob?.destructive ? "destructive" : "default"}
              disabled={dispatching}
              onClick={handleDispatch}
            >
              Confirmar disparo
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
