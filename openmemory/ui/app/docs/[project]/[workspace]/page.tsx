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
import { ArrowLeft, RollerCoaster } from "lucide-react";
import { RootState } from "@/store/store";
import { useSpecsApi } from "@/hooks/useSpecsApi";
import { PageHeader } from "@/components/shared/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { BOARD_COLUMNS, TASK_COLUMN_KEYS, handleCardDrop } from "@/lib/specsBoard";
import { MarkdownViewer } from "@/components/shared/MarkdownViewer";
import type {
  SpecDocument,
  TaskCard,
  TaskCardStatus,
} from "@/types/specs";

const COLUMN_LABEL: Record<string, string> = Object.fromEntries(
  BOARD_COLUMNS.map((c) => [c.key, c.label]),
);

// ---- Card de task (arrastável; clique abre detalhe) ------------------------
function SortableTaskCard({
  task,
  onOpen,
  claimTakenBy,
}: {
  task: TaskCard;
  onOpen: (task: TaskCard) => void;
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
    <button
      type="button"
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      data-testid={`task-card-${task.id}`}
      onClick={() => onOpen(task)}
      className="w-full rounded-md border border-zinc-800 bg-zinc-900 p-3 text-left text-sm transition-colors hover:border-zinc-600 hover:bg-zinc-900/80"
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
    </button>
  );
}

// ---- Card de documento (clique abre) --------------------------------------
function DocumentCard({
  doc,
  onOpen,
}: {
  doc: SpecDocument;
  onOpen: (doc: SpecDocument) => void;
}) {
  return (
    <button
      type="button"
      data-testid={`doc-card-${doc.document_type}`}
      onClick={() => onOpen(doc)}
      className="w-full rounded-md border border-zinc-800 bg-zinc-900 p-3 text-left text-sm transition-colors hover:border-zinc-600 hover:bg-zinc-900/80"
    >
      <div className="font-medium uppercase text-zinc-100">{doc.document_type}</div>
      <div className="mt-1 text-xs text-zinc-400">versão v{doc.current_version}</div>
    </button>
  );
}

// ---- Coluna ----------------------------------------------------------------
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
        "flex min-h-0 min-w-0 flex-1 flex-col gap-2 rounded-lg border border-zinc-800 bg-zinc-950/40 p-2" +
        (isOver ? " ring-2 ring-blue-500" : "")
      }
    >
      <h3 className="shrink-0 px-1 text-xs font-black uppercase tracking-widest text-zinc-400">
        {label}
      </h3>
      <div className="custom-scroll flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}

export default function SpecsBoardPage() {
  const params = useParams<{ project: string; workspace: string }>();
  const project = decodeURIComponent(params.project);
  const workspaceId = params.workspace;

  const {
    updateTaskStatus,
    updateTask,
    deleteTask,
    deleteDocument,
    writeDocument,
    claimTask,
    fetchWorkspaceBoard,
  } = useSpecsApi({
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

  const [tasks, setTasks] = useState<TaskCard[]>([]);
  const [conflictMsg, setConflictMsg] = useState<string | null>(null);
  const [claimTaken, setClaimTaken] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [dialogError, setDialogError] = useState<string | null>(null);

  const [openTask, setOpenTask] = useState<TaskCard | null>(null);
  const [taskTitle, setTaskTitle] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [taskStatus, setTaskStatus] = useState<TaskCardStatus>("tasks");

  const [openDoc, setOpenDoc] = useState<SpecDocument | null>(null);
  const [docContent, setDocContent] = useState("");
  const [docEditing, setDocEditing] = useState(false);
  const [taskDescEditing, setTaskDescEditing] = useState(false);

  useEffect(() => {
    if (board) setTasks(board.tasks);
  }, [board]);

  useEffect(() => {
    if (!openTask) return;
    const fresh = tasks.find((t) => t.id === openTask.id);
    if (fresh) setOpenTask(fresh);
  }, [tasks, openTask?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  );

  const openTaskDialog = useCallback((task: TaskCard) => {
    setDialogError(null);
    setTaskDescEditing(false);
    setOpenTask(task);
    setTaskTitle(task.title);
    setTaskDescription(task.description || "");
    setTaskStatus(task.status);
  }, []);

  const openDocDialog = useCallback((doc: SpecDocument) => {
    setDialogError(null);
    setDocEditing(false);
    setOpenDoc(doc);
    setDocContent(doc.current_content || "");
  }, []);

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
        setConflictMsg(
          `Conflito ao mover "${outcome.task?.title}": o card mudou no servidor (versão ${outcome.result?.current_version}). O quadro foi atualizado.`,
        );
        await fetchWorkspaceBoard(workspaceId);
      } else {
        setConflictMsg(null);
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
      setBusy(true);
      setDialogError(null);
      try {
        const res = await claimTask(task.id, actor);
        if (!res.claimed) {
          setClaimTaken((prev) => ({
            ...prev,
            [task.id]: res.current_assignee || "outro responsável",
          }));
          setDialogError(
            `Já assumida por ${res.current_assignee || "outro responsável"}.`,
          );
        } else {
          setClaimTaken((prev) => {
            const next = { ...prev };
            delete next[task.id];
            return next;
          });
          await fetchWorkspaceBoard(workspaceId);
        }
      } finally {
        setBusy(false);
      }
    },
    [claimTask, actor, fetchWorkspaceBoard, workspaceId],
  );

  const onToggleBlock = useCallback(
    async (task: TaskCard) => {
      setBusy(true);
      setDialogError(null);
      try {
        const res = await updateTaskStatus(task.id, {
          expected_version: task.version,
          new_status: task.status,
          actor,
          is_blocked: !task.is_blocked,
          block_reason: !task.is_blocked ? "Bloqueado via quadro" : null,
        });
        if (res.conflict) {
          setDialogError("Conflito ao atualizar o bloqueio; o quadro foi atualizado.");
        }
        await fetchWorkspaceBoard(workspaceId);
      } finally {
        setBusy(false);
      }
    },
    [updateTaskStatus, actor, fetchWorkspaceBoard, workspaceId],
  );

  const onSaveTask = useCallback(async () => {
    if (!openTask) return;
    setBusy(true);
    setDialogError(null);
    try {
      let version = openTask.version;
      if (
        taskTitle !== openTask.title ||
        taskDescription !== (openTask.description || "")
      ) {
        const res = await updateTask(openTask.id, {
          expected_version: version,
          title: taskTitle,
          description: taskDescription,
        });
        if (res.conflict) {
          setDialogError("Conflito de versão ao salvar. Recarregue o quadro.");
          await fetchWorkspaceBoard(workspaceId);
          return;
        }
        version = res.task?.version ?? version + 1;
      }
      if (taskStatus !== openTask.status) {
        const res = await updateTaskStatus(openTask.id, {
          expected_version: version,
          new_status: taskStatus,
          actor,
        });
        if (res.conflict) {
          setDialogError("Conflito ao mover a coluna. Recarregue o quadro.");
          await fetchWorkspaceBoard(workspaceId);
          return;
        }
      }
      setOpenTask(null);
      await fetchWorkspaceBoard(workspaceId);
    } finally {
      setBusy(false);
    }
  }, [
    openTask,
    taskTitle,
    taskDescription,
    taskStatus,
    updateTask,
    updateTaskStatus,
    actor,
    fetchWorkspaceBoard,
    workspaceId,
  ]);

  const onDeleteTask = useCallback(async () => {
    if (!openTask) return;
    if (!window.confirm(`Excluir a task "${openTask.title}"?`)) return;
    setBusy(true);
    setDialogError(null);
    try {
      await deleteTask(openTask.id);
      setOpenTask(null);
      await fetchWorkspaceBoard(workspaceId);
    } catch (err: any) {
      setDialogError(err?.message || "Falha ao excluir a task");
    } finally {
      setBusy(false);
    }
  }, [openTask, deleteTask, fetchWorkspaceBoard, workspaceId]);

  const onSaveDoc = useCallback(async () => {
    if (!openDoc || !board) return;
    setBusy(true);
    setDialogError(null);
    try {
      const res = await writeDocument(board.workspace.id, openDoc.document_type, {
        content: docContent,
        expected_version: openDoc.current_version,
        author: actor,
      });
      if (res.conflict) {
        setDialogError(
          `Conflito de versão (atual v${res.current_version}). Conteúdo do servidor carregado.`,
        );
        setDocContent(res.current_content || "");
        await fetchWorkspaceBoard(workspaceId);
        return;
      }
      setDocEditing(false);
      setOpenDoc(null);
      await fetchWorkspaceBoard(workspaceId);
    } catch (err: any) {
      setDialogError(err?.message || "Falha ao salvar o documento");
    } finally {
      setBusy(false);
    }
  }, [
    openDoc,
    board,
    docContent,
    writeDocument,
    actor,
    fetchWorkspaceBoard,
    workspaceId,
  ]);

  const onDeleteDoc = useCallback(async () => {
    if (!openDoc || !board) return;
    if (
      !window.confirm(
        `Excluir o documento ${openDoc.document_type.toUpperCase()} (e o histórico de versões)?`,
      )
    ) {
      return;
    }
    setBusy(true);
    setDialogError(null);
    try {
      await deleteDocument(board.workspace.id, openDoc.document_type);
      setOpenDoc(null);
      await fetchWorkspaceBoard(workspaceId);
    } catch (err: any) {
      setDialogError(err?.message || "Falha ao excluir o documento");
    } finally {
      setBusy(false);
    }
  }, [openDoc, board, deleteDocument, fetchWorkspaceBoard, workspaceId]);

  const tasksByColumn = useMemo(() => {
    const map: Record<string, TaskCard[]> = {};
    for (const t of tasks) {
      (map[t.status] ||= []).push(t);
    }
    return map;
  }, [tasks]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
      <div className="shrink-0 space-y-2">
        <Link
          href={`/docs/${encodeURIComponent(project)}`}
          className="inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200"
        >
          <ArrowLeft className="h-4 w-4" /> Painel de {project}
        </Link>
        <PageHeader
          className="mb-0"
          icon={RollerCoaster}
          title={board ? `Quadro — ${board.workspace.name}` : "Quadro"}
          description="Clique para abrir. Arraste tasks entre colunas. Documentos ficam em SDD."
        />
        {error && (
          <p className="text-sm text-red-400" role="alert">
            {error}
          </p>
        )}
        {conflictMsg && (
          <p className="text-sm text-amber-400" role="alert">
            {conflictMsg}
          </p>
        )}
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragEnd={onDragEnd}
      >
        <div className="flex min-h-0 flex-1 gap-2 overflow-hidden">
          {BOARD_COLUMNS.map((col) => (
            <Column key={col.key} columnKey={col.key} label={col.label}>
              {col.isDocuments ? (
                (board?.documents ?? []).map((doc) => (
                  <DocumentCard key={doc.id} doc={doc} onOpen={openDocDialog} />
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
                      onOpen={openTaskDialog}
                      claimTakenBy={claimTaken[t.id]}
                    />
                  ))}
                </SortableContext>
              )}
            </Column>
          ))}
        </div>
      </DndContext>

      {/* Modal Task */}
      <Dialog
        open={!!openTask}
        onOpenChange={(open) => {
          if (!open) setOpenTask(null);
        }}
      >
        <DialogContent className="flex max-h-[85vh] max-w-2xl flex-col gap-4 overflow-hidden border-zinc-800 bg-zinc-950 text-zinc-100">
          <DialogHeader>
            <DialogTitle>Task</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Ver, editar, mover de coluna ou excluir.
            </DialogDescription>
          </DialogHeader>
          {dialogError && (
            <p className="text-sm text-red-400" role="alert">
              {dialogError}
            </p>
          )}
          <div className="custom-scroll min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
            <div className="space-y-1">
              <Label htmlFor="task-title">Título</Label>
              <Input
                id="task-title"
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                className="border-zinc-700 bg-zinc-900"
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="task-status">Coluna</Label>
              <Select
                value={taskStatus}
                onValueChange={(v) => setTaskStatus(v as TaskCardStatus)}
              >
                <SelectTrigger
                  id="task-status"
                  className="border-zinc-700 bg-zinc-900"
                >
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TASK_COLUMN_KEYS.map((key) => (
                    <SelectItem key={key} value={key}>
                      {COLUMN_LABEL[key] || key}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor="task-desc">Descrição</Label>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-xs"
                  onClick={() => setTaskDescEditing((v) => !v)}
                >
                  {taskDescEditing ? "Visualizar" : "Editar MD"}
                </Button>
              </div>
              {taskDescEditing ? (
                <Textarea
                  id="task-desc"
                  value={taskDescription}
                  onChange={(e) => setTaskDescription(e.target.value)}
                  rows={12}
                  className="min-h-[200px] border-zinc-700 bg-zinc-900 font-mono text-xs"
                />
              ) : (
                <MarkdownViewer content={taskDescription} />
              )}
            </div>
            {openTask?.assignee && (
              <p className="text-xs text-zinc-400">
                Responsável: {openTask.assignee}
              </p>
            )}
          </div>
          <DialogFooter className="flex-wrap gap-2 sm:justify-between">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="destructive"
                disabled={busy}
                onClick={onDeleteTask}
              >
                Excluir
              </Button>
              {openTask?.status === "tasks" && !openTask.assignee && (
                <Button
                  variant="outline"
                  disabled={busy || !!claimTaken[openTask.id]}
                  onClick={() => openTask && onClaim(openTask)}
                >
                  Assumir
                </Button>
              )}
              {openTask && (
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => openTask && onToggleBlock(openTask)}
                >
                  {openTask.is_blocked ? "Desbloquear" : "Bloquear"}
                </Button>
              )}
            </div>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => setOpenTask(null)}
              >
                Cancelar
              </Button>
              <Button disabled={busy || !taskTitle.trim()} onClick={onSaveTask}>
                Salvar
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Documento */}
      <Dialog
        open={!!openDoc}
        onOpenChange={(open) => {
          if (!open) {
            setOpenDoc(null);
            setDocEditing(false);
          }
        }}
      >
        <DialogContent className="flex max-h-[90vh] max-w-4xl flex-col gap-4 overflow-hidden border-zinc-800 bg-zinc-950 text-zinc-100">
          <DialogHeader>
            <DialogTitle className="uppercase">
              {openDoc?.document_type}{" "}
              <span className="text-sm font-normal text-zinc-400">
                v{openDoc?.current_version}
              </span>
            </DialogTitle>
            <DialogDescription className="text-zinc-400">
              Documento SDD — visualizar, editar ou excluir.
            </DialogDescription>
          </DialogHeader>
          {dialogError && (
            <p className="text-sm text-red-400" role="alert">
              {dialogError}
            </p>
          )}
          <div className="custom-scroll min-h-0 flex-1 overflow-y-auto">
            {docEditing ? (
              <Textarea
                value={docContent}
                onChange={(e) => setDocContent(e.target.value)}
                className="min-h-[50vh] border-zinc-700 bg-zinc-900 font-mono text-xs"
              />
            ) : (
              <MarkdownViewer
                content={docContent}
                emptyLabel="(documento vazio)"
              />
            )}
          </div>
          <DialogFooter className="flex-wrap gap-2 sm:justify-between">
            <Button variant="destructive" disabled={busy} onClick={onDeleteDoc}>
              Excluir
            </Button>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => {
                  setOpenDoc(null);
                  setDocEditing(false);
                }}
              >
                Fechar
              </Button>
              {docEditing ? (
                <Button disabled={busy} onClick={onSaveDoc}>
                  Salvar
                </Button>
              ) : (
                <Button disabled={busy} onClick={() => setDocEditing(true)}>
                  Editar
                </Button>
              )}
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
