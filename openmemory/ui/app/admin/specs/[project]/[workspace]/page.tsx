"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useSelector } from "react-redux";
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowLeft } from "lucide-react";
import { RootState } from "@/store/store";
import { useSpecsApi } from "@/hooks/useSpecsApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RollerCoaster } from "lucide-react";
import { BOARD_COLUMNS, handleCardDrop } from "@/lib/specsBoard";
import type { SpecDocument, TaskCard } from "@/types/specs";

// ---- Card de task (arrastável) ---------------------------------------------
function SortableTaskCard({
  task,
  onClaim,
  onToggleBlock,
  claimTakenBy,
}: {
  task: TaskCard;
  onClaim: (task: TaskCard) => void;
  onToggleBlock: (task: TaskCard) => void;
  claimTakenBy?: string | null;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: task.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-testid={`task-card-${task.id}`}
      className="rounded-md border border-zinc-800 bg-zinc-900 p-3 text-sm"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium text-zinc-100">{task.title}</span>
        {task.is_blocked && (
          <Badge variant="destructive" aria-label="bloqueado">
            Bloqueado
          </Badge>
        )}
      </div>
      {task.assignee && (
        <div className="mt-1 text-xs text-zinc-400">
          Responsável: <span className="text-zinc-200">{task.assignee}</span>
        </div>
      )}
      {task.block_reason && (
        <div className="mt-1 text-xs text-amber-400">{task.block_reason}</div>
      )}
      {claimTakenBy && (
        <div className="mt-1 text-xs text-red-400" role="alert">
          Já assumida por {claimTakenBy}. Aguarde a atualização do quadro.
        </div>
      )}
      {/* Ações: interrompe o pointerdown para não iniciar drag ao clicar. */}
      <div
        className="mt-2 flex gap-2"
        onPointerDown={(e) => e.stopPropagation()}
      >
        {task.status === "tasks" && !task.assignee && (
          <Button
            size="sm"
            variant="outline"
            disabled={!!claimTakenBy}
            onClick={() => onClaim(task)}
          >
            Assumir
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => onToggleBlock(task)}>
          {task.is_blocked ? "Desbloquear" : "Bloquear"}
        </Button>
      </div>
    </div>
  );
}

// ---- Card de documento (fixo na coluna SDD, não arrastável) -----------------
function DocumentCard({ doc }: { doc: SpecDocument }) {
  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900 p-3 text-sm">
      <div className="font-medium uppercase text-zinc-100">{doc.document_type}</div>
      <div className="mt-1 text-xs text-zinc-400">versão v{doc.current_version}</div>
    </div>
  );
}

// ---- Coluna (zona de drop) --------------------------------------------------
function Column({
  columnKey,
  label,
  children,
}: {
  columnKey: string;
  label: string;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: columnKey });
  return (
    <div
      ref={setNodeRef}
      data-testid={`column-${columnKey}`}
      className={
        "flex w-64 shrink-0 flex-col gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 p-2" +
        (isOver ? " ring-2 ring-blue-500" : "")
      }
    >
      <h3 className="px-1 text-xs font-black uppercase tracking-widest text-zinc-400">
        {label}
      </h3>
      {children}
    </div>
  );
}

export default function SpecsBoardPage() {
  const params = useParams<{ project: string; workspace: string }>();
  const project = decodeURIComponent(params.project);
  const workspaceId = params.workspace;

  const { updateTaskStatus, claimTask, fetchWorkspaceBoard } = useSpecsApi({
    workspaceId,
    poll: true,
  });

  const board = useSelector((s: RootState) => s.specs.currentBoard);
  const error = useSelector((s: RootState) => s.specs.error);
  const actor = useSelector(
    (s: RootState) =>
      s.profile?.person?.machineHostname ||
      s.profile?.person?.email ||
      s.profile?.userId ||
      "ui-user",
  );

  // Cópia local dos cards para UI otimista (reverte em conflito).
  const [tasks, setTasks] = useState<TaskCard[]>([]);
  const [conflictMsg, setConflictMsg] = useState<string | null>(null);
  const [claimTaken, setClaimTaken] = useState<Record<string, string>>({});

  useEffect(() => {
    if (board) setTasks(board.tasks);
  }, [board]);

  const sensors = useSensors(useSensor(PointerSensor));

  const onDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const activeId = String(event.active.id);
      const overColumn = event.over ? String(event.over.id) : null;

      const outcome = await handleCardDrop({
        activeId,
        overColumn,
        tasks,
        actor,
        updateTaskStatus,
      });
      if (!outcome.moved) return;

      if (outcome.conflict) {
        // Reverte visualmente para o estado do servidor e avisa.
        setConflictMsg(
          `Conflito ao mover "${outcome.task?.title}": o card mudou no servidor (versão ${outcome.result?.current_version}). O quadro foi atualizado.`,
        );
        await fetchWorkspaceBoard(workspaceId);
      } else {
        setConflictMsg(null);
        // Aplica otimista e ressincroniza com o servidor.
        setTasks((prev) =>
          prev.map((t) =>
            t.id === outcome.task?.id
              ? { ...t, status: outcome.targetStatus!, version: t.version + 1 }
              : t,
          ),
        );
        await fetchWorkspaceBoard(workspaceId);
      }
    },
    [tasks, actor, updateTaskStatus, fetchWorkspaceBoard, workspaceId],
  );

  const onClaim = useCallback(
    async (task: TaskCard) => {
      const res = await claimTask(task.id, actor);
      if (!res.claimed) {
        setClaimTaken((prev) => ({
          ...prev,
          [task.id]: res.current_assignee || "outro responsável",
        }));
      } else {
        setClaimTaken((prev) => {
          const next = { ...prev };
          delete next[task.id];
          return next;
        });
        await fetchWorkspaceBoard(workspaceId);
      }
    },
    [claimTask, actor, fetchWorkspaceBoard, workspaceId],
  );

  const onToggleBlock = useCallback(
    async (task: TaskCard) => {
      const res = await updateTaskStatus(task.id, {
        expected_version: task.version,
        new_status: task.status,
        actor,
        is_blocked: !task.is_blocked,
        block_reason: !task.is_blocked ? "Bloqueado via quadro" : null,
      });
      if (res.conflict) {
        setConflictMsg("Conflito ao atualizar o bloqueio; o quadro foi atualizado.");
      }
      await fetchWorkspaceBoard(workspaceId);
    },
    [updateTaskStatus, actor, fetchWorkspaceBoard, workspaceId],
  );

  const tasksByColumn = useMemo(() => {
    const map: Record<string, TaskCard[]> = {};
    for (const t of tasks) {
      (map[t.status] ||= []).push(t);
    }
    return map;
  }, [tasks]);

  return (
    <div>
      <Link
        href={`/admin/specs/${encodeURIComponent(project)}`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200"
      >
        <ArrowLeft className="h-4 w-4" /> Painel de {project}
      </Link>
      <PageHeader
        className="mb-4"
        icon={RollerCoaster}
        title={board ? `Quadro — ${board.workspace.name}` : "Quadro"}
        description="Arraste os cards de task entre as colunas. Documentos ficam fixos em SDD."
      />

      {error && (
        <p className="mb-3 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}
      {conflictMsg && (
        <p className="mb-3 text-sm text-amber-400" role="alert">
          {conflictMsg}
        </p>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragEnd={onDragEnd}
      >
        <div className="flex gap-3 overflow-x-auto pb-4">
          {BOARD_COLUMNS.map((col) => (
            <Column key={col.key} columnKey={col.key} label={col.label}>
              {col.isDocuments ? (
                (board?.documents ?? []).map((doc) => (
                  <DocumentCard key={doc.id} doc={doc} />
                ))
              ) : (
                <SortableContext
                  items={(tasksByColumn[col.key] ?? []).map((t) => t.id)}
                  strategy={verticalListSortingStrategy}
                >
                  {(tasksByColumn[col.key] ?? []).map((t) => (
                    <SortableTaskCard
                      key={t.id}
                      task={t}
                      onClaim={onClaim}
                      onToggleBlock={onToggleBlock}
                      claimTakenBy={claimTaken[t.id]}
                    />
                  ))}
                </SortableContext>
              )}
            </Column>
          ))}
        </div>
      </DndContext>
    </div>
  );
}
