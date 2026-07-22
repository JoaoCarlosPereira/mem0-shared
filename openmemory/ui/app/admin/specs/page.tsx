"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useSelector } from "react-redux";
import { ClipboardList } from "lucide-react";
import { RootState } from "@/store/store";
import { useSpecsApi } from "@/hooks/useSpecsApi";
import { PageHeader } from "@/components/shared/PageHeader";
import type { TaskCardStatus, WorkspaceSummary } from "@/types/specs";

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
  if (total === 0) return <span className="text-zinc-500">sem tasks</span>;
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

export default function SpecsIndexPage() {
  // Auto-atualiza o índice global (todos os projetos) via polling.
  useSpecsApi({ all: true, poll: true });

  const workspaces = useSelector((s: RootState) => s.specs.allWorkspaces);
  const loading = useSelector((s: RootState) => s.specs.loading);
  const error = useSelector((s: RootState) => s.specs.error);

  // Agrupa os quadros por projeto para exibição.
  const byProject = useMemo(() => {
    const map = new Map<string, WorkspaceSummary[]>();
    for (const ws of workspaces ?? []) {
      const arr = map.get(ws.project_id) ?? [];
      arr.push(ws);
      map.set(ws.project_id, arr);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [workspaces]);

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={ClipboardList}
        title="Specs"
        description="Quadros de especificações (PRD/TechSpec/Tasks) por Tarefa, agrupados por projeto. Clique num quadro para abrir o Kanban."
      />

      {error && (
        <p className="mb-3 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}

      {workspaces === null && loading ? (
        <p className="py-8 text-center text-zinc-500">Carregando…</p>
      ) : !workspaces || workspaces.length === 0 ? (
        <p className="py-8 text-center text-zinc-500">
          Nenhuma spec ainda. Crie uma com as skills /cy-create-prd,
          /cy-create-techspec e /cy-create-tasks.
        </p>
      ) : (
        <div className="space-y-6">
          {byProject.map(([project, wss]) => (
            <section key={project}>
              <div className="mb-2 flex items-center gap-2">
                <h2 className="text-sm font-black uppercase tracking-widest text-zinc-400">
                  {project}
                </h2>
                <Link
                  href={`/admin/specs/${encodeURIComponent(project)}`}
                  className="text-xs text-blue-400 hover:text-blue-300 hover:underline"
                >
                  ver painel
                </Link>
              </div>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                {wss.map((ws) => (
                  <Link
                    key={ws.id}
                    href={`/admin/specs/${encodeURIComponent(project)}/${ws.id}`}
                    className="block rounded-lg border border-zinc-800 bg-zinc-900 p-4 transition-colors hover:border-blue-600"
                    data-testid={`spec-card-${ws.id}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-zinc-100">{ws.name}</span>
                      <span className="text-xs text-zinc-400">
                        {STATUS_LABEL[ws.status] ?? ws.status}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-zinc-500">{ws.slug}</div>
                    <div className="mt-3">
                      <TaskCounts counts={ws.task_counts} />
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
