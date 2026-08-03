"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useSelector } from "react-redux";
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  TouchSensor,
  closestCorners,
  pointerWithin,
  rectIntersection,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
  type CollisionDetection,
} from "@dnd-kit/core";
import { ArrowLeft, GripVertical, Plus, RollerCoaster } from "lucide-react";
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
import {
  BOARD_COLUMNS,
  TASK_COLUMN_KEYS,
  handleCardDrop,
  pickBoardDropTarget,
  resolveDropColumn,
  sortTasksByPosition,
} from "@/lib/specsBoard";
import { MarkdownViewer } from "@/components/shared/MarkdownViewer";
import { ActorLabel } from "@/components/shared/attribution-badge";
import { TaskRichFields } from "@/components/docs/TaskRichFields";
import type {
  SpecDocument,
  TaskCard,
  TaskCardStatus,
} from "@/types/specs";
import { cn } from "@/lib/utils";

function toDatetimeLocal(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromDatetimeLocal(local: string): string | null {
  const raw = local.trim();
  if (!raw) return null;
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}

/** Prefer pointer-within (empty columns + cards), then intersection, then corners. */
const boardCollisionDetection: CollisionDetection = (args) => {
  const pointerHits = pointerWithin(args);
  const rectHits = pointerHits.length > 0 ? pointerHits : rectIntersection(args);
  const raw = rectHits.length > 0 ? rectHits : closestCorners(args);

  const enriched = raw.map((hit) => {
    const container = args.droppableContainers.find((c) => c.id === hit.id);
    return {
      id: hit.id,
      data: (container?.data.current ?? null) as {
        type?: string;
        status?: string;
      } | null,
    };
  });
  const preferred = pickBoardDropTarget(enriched);
  if (!preferred) return raw;
  const match = raw.find((h) => String(h.id) === preferred);
  return match ? [match] : raw;
};

const COLUMN_LABEL: Record<string, string> = Object.fromEntries(
  BOARD_COLUMNS.map((c) => [c.key, c.label]),
);

// ---- Conteúdo visual do card (reutilizado no overlay) ---------------------
function TaskCardBody({
  task,
  claimTakenBy,
  claimBusy,
  onOpen,
  onClaim,
  dragHandle,
}: {
  task: TaskCard;
  claimTakenBy?: string | null;
  claimBusy?: boolean;
  onOpen?: (task: TaskCard) => void;
  onClaim?: (task: TaskCard) => void;
  dragHandle?: React.ReactNode;
}) {
  const canClaim = task.status === "tasks" && !task.assignee && !!onClaim;

  return (
    <>
      <div className="flex items-start gap-1.5">
        {dragHandle}
        <div className="min-w-0 flex-1">
          {onOpen ? (
            <button
              type="button"
              onClick={() => onOpen(task)}
              className="w-full text-left"
              data-testid={`task-card-open-${task.id}`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium text-foreground">{task.title}</span>
                {task.is_blocked && (
                  <Badge variant="destructive" aria-label="bloqueado">
                    Bloqueado
                  </Badge>
                )}
              </div>
            </button>
          ) : (
            <div className="flex items-start justify-between gap-2">
              <span className="font-medium text-foreground">{task.title}</span>
              {task.is_blocked && (
                <Badge variant="destructive" aria-label="bloqueado">
                  Bloqueado
                </Badge>
              )}
            </div>
          )}
          {task.assignee && (
            <div className="mt-2" data-testid={`task-assignee-${task.id}`}>
              <ActorLabel
                hostname={task.assignee}
                displayName={task.assignee_display_name}
                avatarUrl={task.assignee_avatar_url}
              />
            </div>
          )}
          {task.due_at && (
            <div
              className="mt-1 text-xs text-muted-foreground"
              data-testid={`task-due-${task.id}`}
            >
              Prazo {new Date(task.due_at).toLocaleString()}
            </div>
          )}
          {task.members && task.members.length > 0 && (
            <div className="mt-1 text-xs text-muted-foreground">
              {task.members.join(", ")}
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
        </div>
      </div>
      {canClaim && (
        <div className="mt-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-7 w-full border-zinc-700 text-xs"
            disabled={claimBusy || !!claimTakenBy}
            data-testid={`claim-card-${task.id}`}
            onPointerDown={(e) => e.stopPropagation()}
            onClick={(e) => {
              e.stopPropagation();
              onClaim?.(task);
            }}
          >
            Assumir
          </Button>
        </div>
      )}
    </>
  );
}

// ---- Card de task (arrastável; clique no título abre detalhe) --------------
function DraggableTaskCard({
  task,
  onOpen,
  onClaim,
  claimTakenBy,
  claimBusy,
}: {
  task: TaskCard;
  onOpen: (task: TaskCard) => void;
  onClaim?: (task: TaskCard) => void;
  claimTakenBy?: string | null;
  claimBusy?: boolean;
}) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: task.id,
    data: { type: "task", status: task.status },
  });
  // Também droppable: soltar sobre outro card resolve a coluna via resolveDropColumn
  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: task.id,
    data: { type: "task", status: task.status },
  });
  const setRefs = useCallback(
    (node: HTMLElement | null) => {
      setNodeRef(node);
      setDropRef(node);
    },
    [setNodeRef, setDropRef],
  );

  return (
    <div
      ref={setRefs}
      {...listeners}
      {...attributes}
      data-testid={`task-card-${task.id}`}
      className={cn(
        "w-full touch-none rounded-md border border-border bg-card p-3 text-left text-sm text-card-foreground transition-colors hover:border-primary/40 hover:bg-card/80",
        isDragging ? "cursor-grabbing opacity-40" : "cursor-grab",
        isOver && !isDragging && "ring-2 ring-primary/60",
      )}
    >
      <TaskCardBody
        task={task}
        claimTakenBy={claimTakenBy}
        claimBusy={claimBusy}
        onOpen={onOpen}
        onClaim={onClaim}
        dragHandle={
          <span
            aria-hidden
            className="mt-0.5 shrink-0 text-zinc-600"
            data-testid={`task-drag-handle-${task.id}`}
          >
            <GripVertical className="h-4 w-4" />
          </span>
        }
      />
    </div>
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
      className="w-full rounded-md border border-border bg-card p-3 text-left text-sm text-card-foreground transition-colors hover:border-primary/40 hover:bg-card/80"
    >
      <div className="font-medium uppercase text-zinc-100">{doc.document_type}</div>
      <div className="mt-1 text-xs text-zinc-400">versão v{doc.current_version}</div>
      {doc.updated_by && (
        <div className="mt-2" data-testid={`doc-author-${doc.document_type}`}>
          <ActorLabel
            hostname={doc.updated_by}
            displayName={doc.updated_by_display_name}
            avatarUrl={doc.updated_by_avatar_url}
          />
        </div>
      )}
    </button>
  );
}

// ---- Coluna ----------------------------------------------------------------
function Column({
  columnKey,
  label,
  children,
  headerAction,
  isDropTarget,
  acceptsDrops,
}: {
  columnKey: string;
  label: string;
  children: React.ReactNode;
  headerAction?: React.ReactNode;
  isDropTarget?: boolean;
  acceptsDrops?: boolean;
}) {
  const { setNodeRef, isOver } = useDroppable({
    id: columnKey,
    data: { type: "column", status: columnKey },
    disabled: acceptsDrops === false,
  });
  const highlight = acceptsDrops !== false && (isDropTarget || isOver);
  return (
    <div
      ref={setNodeRef}
      data-testid={`column-${columnKey}`}
      className={cn(
        "flex min-h-0 min-w-0 flex-1 flex-col gap-2 rounded-lg border border-border bg-muted/30 p-2 transition-[box-shadow,border-color]",
        highlight && "border-primary/60 ring-2 ring-primary",
      )}
    >
      <div className="flex shrink-0 items-center justify-between gap-1 px-1">
        <h3 className="text-xs font-black uppercase tracking-widest text-muted-foreground">
          {label}
        </h3>
        {headerAction}
      </div>
      <div className="custom-scroll flex min-h-[120px] min-w-0 flex-1 flex-col gap-2 overflow-y-auto">
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
    releaseTask,
    createTask,
    fetchWorkspaceBoard,
    listLabels,
    createLabel,
    attachLabel,
    detachLabel,
    listChecklists,
    createChecklist,
    createChecklistItem,
    patchChecklistItem,
    uploadAttachment,
    deleteAttachment,
    attachmentDownloadUrl,
  } = useSpecsApi({
    workspaceId,
    poll: true,
  });

  const richApi = useMemo(
    () => ({
      listLabels,
      createLabel,
      attachLabel,
      detachLabel,
      listChecklists,
      createChecklist,
      createChecklistItem,
      patchChecklistItem,
      uploadAttachment,
      deleteAttachment,
      attachmentDownloadUrl,
    }),
    [
      listLabels,
      createLabel,
      attachLabel,
      detachLabel,
      listChecklists,
      createChecklist,
      createChecklistItem,
      patchChecklistItem,
      uploadAttachment,
      deleteAttachment,
      attachmentDownloadUrl,
    ],
  );

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
  const [taskDueAt, setTaskDueAt] = useState("");
  const [taskMembersText, setTaskMembersText] = useState("");
  const [taskDescEditing, setTaskDescEditing] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createDescription, setCreateDescription] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);

  const [openDoc, setOpenDoc] = useState<SpecDocument | null>(null);
  const [docContent, setDocContent] = useState("");
  const [docEditing, setDocEditing] = useState(false);
  const [pendingAdrScroll, setPendingAdrScroll] = useState<string | null>(null);
  const [activeDragTask, setActiveDragTask] = useState<TaskCard | null>(null);
  const [overColumnKey, setOverColumnKey] = useState<TaskCardStatus | null>(null);

  useEffect(() => {
    if (board) setTasks(board.tasks);
  }, [board]);

  useEffect(() => {
    if (!openTask) return;
    const fresh = tasks.find((t) => t.id === openTask.id);
    if (fresh) setOpenTask(fresh);
  }, [tasks, openTask?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 180, tolerance: 8 },
    }),
  );

  const clearDragState = useCallback(() => {
    setActiveDragTask(null);
    setOverColumnKey(null);
  }, []);

  const syncOverColumn = useCallback(
    (overId: string | null) => {
      setOverColumnKey(resolveDropColumn(overId, tasks));
    },
    [tasks],
  );

  const onDragStart = useCallback(
    (event: DragStartEvent) => {
      const id = String(event.active.id);
      const task = tasks.find((t) => t.id === id) ?? null;
      setActiveDragTask(task);
      setOverColumnKey(task?.status ?? null);
    },
    [tasks],
  );

  const onDragOver = useCallback(
    (event: DragOverEvent) => {
      const overId = event.over ? String(event.over.id) : null;
      syncOverColumn(overId);
    },
    [syncOverColumn],
  );

  const openTaskDialog = useCallback((task: TaskCard) => {
    setDialogError(null);
    setTaskDescEditing(false);
    setOpenTask(task);
    setTaskTitle(task.title);
    setTaskDescription(task.description || "");
    setTaskStatus(task.status);
    setTaskDueAt(toDatetimeLocal(task.due_at));
    setTaskMembersText((task.members || []).join(", "));
  }, []);

  const openDocDialog = useCallback((doc: SpecDocument) => {
    setDialogError(null);
    setDocEditing(false);
    setOpenDoc(doc);
    setDocContent(doc.current_content || "");
  }, []);

  const openAdrDocument = useCallback(
    (adrSlug: string) => {
      const adrsDoc = (board?.documents ?? []).find((d) => d.document_type === "adrs");
      if (!adrsDoc) {
        setDialogError(
          `Documento ADRs ainda não existe neste workspace. Grave com write_spec_document(..., document_type="adrs").`,
        );
        return;
      }
      setPendingAdrScroll(adrSlug);
      openDocDialog(adrsDoc);
    },
    [board?.documents, openDocDialog],
  );

  useEffect(() => {
    if (!openDoc || openDoc.document_type !== "adrs" || !pendingAdrScroll || docEditing) {
      return;
    }
    const id = pendingAdrScroll;
    const t = window.setTimeout(() => {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      setPendingAdrScroll(null);
    }, 80);
    return () => window.clearTimeout(t);
  }, [openDoc, pendingAdrScroll, docEditing, docContent]);

  const onDragEnd = useCallback(
    async (event: DragEndEvent) => {
      const activeId = String(event.active.id);
      const overColumn = event.over ? String(event.over.id) : null;
      clearDragState();

      const outcome = await handleCardDrop({
        activeId,
        overColumn,
        tasks,
        actor,
        updateTaskStatus,
        updateTask,
        claimTask,
        releaseTask,
      });
      if (!outcome.moved) return;

      if (outcome.claimedDenied) {
        setClaimTaken((prev) => ({
          ...prev,
          [outcome.task!.id]: outcome.currentAssignee || "outro responsável",
        }));
        setConflictMsg(
          `Não foi possível assumir "${outcome.task?.title}": já está com ${outcome.currentAssignee || "outro responsável"}.`,
        );
        await fetchWorkspaceBoard(workspaceId);
      } else if (outcome.conflict) {
        setConflictMsg(
          `Conflito ao mover "${outcome.task?.title}": o card mudou no servidor (versão ${outcome.result?.current_version}). O quadro foi atualizado.`,
        );
        await fetchWorkspaceBoard(workspaceId);
      } else {
        setConflictMsg(null);
        setTasks((prev) =>
          prev.map((t) =>
            t.id === outcome.task?.id
              ? {
                  ...t,
                  ...(outcome.targetStatus
                    ? { status: outcome.targetStatus }
                    : {}),
                  ...(typeof outcome.position === "number"
                    ? { position: outcome.position }
                    : {}),
                  version: outcome.task?.version ?? t.version + 1,
                }
              : t,
          ),
        );
        await fetchWorkspaceBoard(workspaceId);
      }
    },
    [
      tasks,
      actor,
      updateTaskStatus,
      updateTask,
      claimTask,
      releaseTask,
      fetchWorkspaceBoard,
      workspaceId,
      clearDragState,
    ],
  );

  const onDragCancel = useCallback(() => {
    clearDragState();
  }, [clearDragState]);

  const onClaim = useCallback(
    async (task: TaskCard) => {
      setBusy(true);
      setDialogError(null);
      setConflictMsg(null);
      try {
        const res = await claimTask(task.id, actor);
        if (!res.claimed) {
          setClaimTaken((prev) => ({
            ...prev,
            [task.id]: res.current_assignee || "outro responsável",
          }));
          const msg = `Já assumida por ${res.current_assignee || "outro responsável"}.`;
          setDialogError(msg);
          setConflictMsg(`Não foi possível assumir "${task.title}": ${msg}`);
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

  const openCreateDialog = useCallback(() => {
    setCreateError(null);
    setCreateTitle("");
    setCreateDescription("");
    setCreateOpen(true);
  }, []);

  const onCreateTask = useCallback(async () => {
    const title = createTitle.trim();
    if (!title) {
      setCreateError("Informe um título.");
      return;
    }
    setBusy(true);
    setCreateError(null);
    try {
      await createTask({
        workspace_id: workspaceId,
        title,
        description: createDescription.trim() || null,
      });
      setCreateOpen(false);
      await fetchWorkspaceBoard(workspaceId);
    } catch (err: any) {
      setCreateError(err?.message || "Falha ao criar a task");
    } finally {
      setBusy(false);
    }
  }, [createTitle, createDescription, createTask, workspaceId, fetchWorkspaceBoard]);

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
      const nextDue = fromDatetimeLocal(taskDueAt);
      const nextMembers = taskMembersText
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const prevMembers = openTask.members || [];
      const membersChanged =
        nextMembers.join("\0") !== prevMembers.join("\0");
      const dueChanged = toDatetimeLocal(openTask.due_at) !== taskDueAt;

      if (
        taskTitle !== openTask.title ||
        taskDescription !== (openTask.description || "") ||
        dueChanged ||
        membersChanged
      ) {
        const res = await updateTask(openTask.id, {
          expected_version: version,
          title: taskTitle,
          description: taskDescription,
          ...(dueChanged
            ? taskDueAt.trim() && nextDue
              ? { due_at: nextDue }
              : { clear_due_at: true }
            : {}),
          ...(membersChanged ? { members: nextMembers } : {}),
        });
        if (res.conflict) {
          setDialogError("Conflito de versão ao salvar. Recarregue o quadro.");
          await fetchWorkspaceBoard(workspaceId);
          return;
        }
        version = res.task?.version ?? version + 1;
      }
      if (taskStatus !== openTask.status) {
        if (taskStatus === "em_andamento" && openTask.status === "tasks") {
          const res = await claimTask(openTask.id, actor);
          if (!res.claimed) {
            setDialogError(
              `Já assumida por ${res.current_assignee || "outro responsável"}.`,
            );
            await fetchWorkspaceBoard(workspaceId);
            return;
          }
        } else if (taskStatus === "tasks") {
          await releaseTask(openTask.id, {
            actor,
            reason: "move via dialog",
          });
        } else {
          const res = await updateTaskStatus(openTask.id, {
            expected_version: version,
            new_status: taskStatus,
            actor,
          });
          if (res.conflict) {
            setDialogError(
              res.current_status
                ? "Conflito ao mover a coluna. Recarregue o quadro."
                : "Transição inválida (use claim/release para em_andamento/backlog).",
            );
            await fetchWorkspaceBoard(workspaceId);
            return;
          }
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
    taskDueAt,
    taskMembersText,
    updateTask,
    updateTaskStatus,
    claimTask,
    releaseTask,
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
    for (const key of Object.keys(map)) {
      map[key] = sortTasksByPosition(map[key]);
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
          description="Modo Spec: trilho SDD (prd/techspec/tasks/adrs) + pipeline Kanban. Clique para abrir. Arraste tasks entre colunas — só via FastAPI."
        />
        <p
          className="text-xs text-muted-foreground"
          data-testid="spec-mode-rail-hint"
        >
          Pipeline: Tasks → Em andamento → Revisão → Teste → Concluído. Documentos
          ficam em SDD (não arrastáveis).
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            onClick={openCreateDialog}
            data-testid="create-task-btn"
            className="gap-1"
          >
            <Plus className="h-4 w-4" />
            Nova task
          </Button>
        </div>
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
        collisionDetection={boardCollisionDetection}
        onDragStart={onDragStart}
        onDragOver={onDragOver}
        onDragEnd={onDragEnd}
        onDragCancel={onDragCancel}
      >
        <div className="flex min-h-0 flex-1 gap-2 overflow-hidden">
          {BOARD_COLUMNS.map((col) => (
            <Column
              key={col.key}
              columnKey={col.key}
              label={col.label}
              acceptsDrops={!col.isDocuments}
              isDropTarget={
                !col.isDocuments && overColumnKey === col.key && !!activeDragTask
              }
              headerAction={
                col.key === "tasks" ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="h-6 px-1.5 text-zinc-400 hover:text-zinc-100"
                    onClick={openCreateDialog}
                    aria-label="Nova task"
                    data-testid="create-task-column-btn"
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                ) : null
              }
            >
              {col.isDocuments ? (
                (board?.documents ?? []).map((doc) => (
                  <DocumentCard key={doc.id} doc={doc} onOpen={openDocDialog} />
                ))
              ) : (
                (tasksByColumn[col.key] ?? []).map((t) => (
                  <DraggableTaskCard
                    key={t.id}
                    task={t}
                    onOpen={openTaskDialog}
                    onClaim={onClaim}
                    claimTakenBy={claimTaken[t.id]}
                    claimBusy={busy}
                  />
                ))
              )}
            </Column>
          ))}
        </div>
        <DragOverlay dropAnimation={null}>
          {activeDragTask ? (
            <div
              data-testid="task-drag-overlay"
              className="w-[220px] cursor-grabbing rounded-md border border-blue-500/50 bg-zinc-900 p-3 text-left text-sm shadow-xl shadow-black/50 ring-2 ring-blue-500/40"
            >
              <TaskCardBody task={activeDragTask} />
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* Modal criar Task */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg border-zinc-800 bg-zinc-950 text-zinc-100">
          <DialogHeader>
            <DialogTitle>Nova task</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Cria um card na coluna Tasks.
            </DialogDescription>
          </DialogHeader>
          {createError && (
            <p className="text-sm text-red-400" role="alert">
              {createError}
            </p>
          )}
          <div className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="create-task-title">Título</Label>
              <Input
                id="create-task-title"
                value={createTitle}
                onChange={(e) => setCreateTitle(e.target.value)}
                placeholder="Ex.: Implementar endpoint X"
                className="border-zinc-700 bg-zinc-900"
                autoFocus
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="create-task-desc">Descrição (opcional)</Label>
              <Textarea
                id="create-task-desc"
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                rows={6}
                className="border-zinc-700 bg-zinc-900 font-mono text-xs"
              />
            </div>
          </div>
          <DialogFooter className="gap-2">
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => setCreateOpen(false)}
            >
              Cancelar
            </Button>
            <Button
              disabled={busy || !createTitle.trim()}
              onClick={onCreateTask}
              data-testid="create-task-submit"
            >
              Criar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Modal Task */}
      <Dialog
        open={!!openTask}
        onOpenChange={(open) => {
          if (!open) setOpenTask(null);
        }}
      >
        <DialogContent className="flex max-h-[85vh] max-w-2xl flex-col gap-4 overflow-hidden border-border bg-background text-foreground">
          <DialogHeader>
            <DialogTitle>Task</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              Ver, editar, mover de coluna ou excluir. Campos ricos via FastAPI.
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
                <MarkdownViewer
                  content={taskDescription}
                  onAdrLink={openAdrDocument}
                />
              )}
            </div>
            {openTask?.assignee && (
              <div data-testid="task-detail-assignee">
                <ActorLabel
                  hostname={openTask.assignee}
                  displayName={openTask.assignee_display_name}
                  avatarUrl={openTask.assignee_avatar_url}
                />
              </div>
            )}
            {openTask && (
              <TaskRichFields
                task={openTask}
                workspaceId={workspaceId}
                api={richApi}
                dueAt={taskDueAt}
                membersText={taskMembersText}
                onDueAtChange={setTaskDueAt}
                onMembersTextChange={setTaskMembersText}
                busy={busy}
              />
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
            setPendingAdrScroll(null);
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
              {openDoc?.document_type === "adrs"
                ? "ADRs do workspace — acessíveis pelos links nos specs (não são cards Kanban)."
                : "Documento SDD — visualizar, editar ou excluir."}
            </DialogDescription>
            {openDoc?.updated_by && (
              <div data-testid="doc-detail-author">
                <ActorLabel
                  hostname={openDoc.updated_by}
                  displayName={openDoc.updated_by_display_name}
                  avatarUrl={openDoc.updated_by_avatar_url}
                />
              </div>
            )}
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
                onAdrLink={
                  openDoc?.document_type === "adrs" ? undefined : openAdrDocument
                }
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
