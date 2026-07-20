"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useSelector } from "react-redux";
import { RollerCoaster } from "lucide-react";
import { RootState } from "@/store/store";
import { useSpecsApi } from "@/hooks/useSpecsApi";
import { PageHeader } from "@/components/shared/PageHeader";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { TaskCardStatus, WorkspaceSummary } from "@/types/specs";

// Colunas fixas do quadro (ADR-001/ADR-007), na ordem de exibição.
const COLUMNS: { key: TaskCardStatus; label: string }[] = [
  { key: "tasks", label: "Tasks" },
  { key: "em_andamento", label: "Em andamento" },
  { key: "revisao_codigo", label: "Revisão de código" },
  { key: "fase_teste", label: "Fase de teste" },
  { key: "concluido", label: "Concluído" },
];

const STATUS_LABEL: Record<string, string> = {
  planejamento: "Planejamento",
  ativo: "Ativo",
  concluido: "Concluído",
  arquivado: "Arquivado",
};

function TaskCounts({ counts }: { counts: WorkspaceSummary["task_counts"] }) {
  const total = COLUMNS.reduce((acc, c) => acc + (counts[c.key] || 0), 0);
  if (total === 0) {
    return <span className="text-zinc-500">sem tasks</span>;
  }
  return (
    <span className="flex flex-wrap gap-2">
      {COLUMNS.filter((c) => (counts[c.key] || 0) > 0).map((c) => (
        <span
          key={c.key}
          className="inline-flex items-center gap-1 rounded-md bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300"
        >
          {c.label}: <strong className="text-zinc-100">{counts[c.key]}</strong>
        </span>
      ))}
    </span>
  );
}

export default function ProjectSpecsPanel() {
  const params = useParams<{ project: string }>();
  const project = decodeURIComponent(params.project);

  // Auto-atualiza o painel via polling (ADR-007) e despacha para o specsSlice.
  useSpecsApi({ projectId: project, poll: true });

  const workspaces = useSelector(
    (s: RootState) => s.specs.projectWorkspaces,
  );
  const loading = useSelector((s: RootState) => s.specs.loading);
  const error = useSelector((s: RootState) => s.specs.error);

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={RollerCoaster}
        title={`Specs — ${project}`}
        description="Tarefas do projeto (SpecWorkspaces) com progresso resumido por coluna do quadro."
      />

      {error && (
        <p className="mb-3 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}

      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Tarefa</TableHead>
              <TableHead className="w-32">Status</TableHead>
              <TableHead>Progresso</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {workspaces === null && loading ? (
              <TableRow>
                <TableCell colSpan={3} className="py-8 text-center text-zinc-500">
                  Carregando…
                </TableCell>
              </TableRow>
            ) : !workspaces || workspaces.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3} className="py-8 text-center text-zinc-500">
                  Nenhuma Tarefa neste projeto
                </TableCell>
              </TableRow>
            ) : (
              workspaces.map((ws) => (
                <TableRow key={ws.id}>
                  <TableCell className="text-zinc-200">
                    <Link
                      href={`/admin/specs/${encodeURIComponent(project)}/${ws.id}`}
                      className="font-medium text-blue-400 hover:text-blue-300 hover:underline"
                    >
                      {ws.name}
                    </Link>
                    <div className="text-xs text-zinc-500">{ws.slug}</div>
                  </TableCell>
                  <TableCell className="text-zinc-300">
                    {STATUS_LABEL[ws.status] ?? ws.status}
                  </TableCell>
                  <TableCell>
                    <TaskCounts counts={ws.task_counts} />
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {workspaces && workspaces.length > 0 && (
        <p className="mt-2 text-xs text-zinc-500">
          {workspaces.length} Tarefa(s).
        </p>
      )}
    </div>
  );
}
