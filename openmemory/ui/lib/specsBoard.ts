// Lógica pura do quadro Kanban de specs (task_14). Colunas fixas do sistema
// (ADR-001/ADR-007), sem customização por projeto no MVP. Separada da UI para
// ser testável sem simular drag-and-drop real (impraticável em jsdom).

import type { TaskCard, TaskCardStatus, TaskUpdate, UpdateStatusResult } from "@/types/specs";
import { computeInsertPosition, sortTasksByPosition } from "@/lib/specsPosition";

export interface BoardColumn {
  key: string; // "SDD" ou um TaskCardStatus
  label: string;
  isDocuments?: boolean; // coluna SDD: só documentos, cards não arrastáveis
}

export const BOARD_COLUMNS: BoardColumn[] = [
  { key: "SDD", label: "SDD", isDocuments: true },
  { key: "tasks", label: "Tasks" },
  { key: "em_andamento", label: "Em andamento" },
  { key: "revisao_codigo", label: "Revisão de código" },
  { key: "fase_teste", label: "Fase de teste" },
  { key: "concluido", label: "Concluído" },
];

export const TASK_COLUMN_KEYS: TaskCardStatus[] = [
  "tasks",
  "em_andamento",
  "revisao_codigo",
  "fase_teste",
  "concluido",
];

export function isTaskColumn(key: string): key is TaskCardStatus {
  return (TASK_COLUMN_KEYS as string[]).includes(key);
}

/**
 * Resolve a coluna-alvo do drop. O ``over.id`` do dnd-kit pode ser:
 * - o id da coluna (``tasks``, ``em_andamento``, …) ao soltar no vazio;
 * - o id de outro card ao soltar sobre um card — neste caso usamos o status
 *   daquele card como coluna de destino.
 */
export function resolveDropColumn(
  overId: string | null,
  tasks: TaskCard[],
): TaskCardStatus | null {
  if (!overId) return null;
  if (isTaskColumn(overId)) return overId;
  const overTask = tasks.find((t) => t.id === overId);
  return overTask ? overTask.status : null;
}

export type BoardCollisionHit = {
  id: string | number;
  data?: { type?: string; status?: string } | null;
};

/**
 * Escolhe o melhor alvo entre colisões do dnd-kit para o quadro Kanban.
 * Prefere card (type=task) quando o ponteiro está sobre um; senão coluna de task.
 * Ignora SDD e ids desconhecidos.
 */
export function pickBoardDropTarget(
  hits: BoardCollisionHit[],
): string | null {
  if (!hits.length) return null;
  const cardHit = hits.find((h) => h.data?.type === "task");
  if (cardHit) return String(cardHit.id);
  const columnHit = hits.find(
    (h) => h.data?.type === "column" && isTaskColumn(String(h.id)),
  );
  if (columnHit) return String(columnHit.id);
  for (const h of hits) {
    const id = String(h.id);
    if (isTaskColumn(id)) return id;
  }
  return null;
}

export interface CardDropOutcome {
  moved: boolean; // a chamada de atualização foi disparada
  conflict: boolean; // servidor rejeitou por conflito de versão (409)
  task?: TaskCard;
  targetStatus?: TaskCardStatus;
  position?: number;
  result?: UpdateStatusResult;
  claimedDenied?: boolean;
  currentAssignee?: string | null;
}

/**
 * Decide e efetiva o resultado de soltar um card de task numa coluna.
 *
 * - Ignora drops sem alvo ou em card de documento (moved=false).
 * - Reordenação na mesma coluna (over = outro card) persiste ``position``.
 * - ``tasks`` → ``em_andamento`` usa ``claimTask`` (exclusividade ADR-003).
 * - Qualquer coluna → ``tasks`` usa ``releaseTask``.
 * - Demais transições usam ``updateTaskStatus`` com concorrência otimista.
 * - Após mudança de coluna (ou reorder), ``updateTask`` grava ``position``.
 */
export async function handleCardDrop(params: {
  activeId: string;
  /** Id da coluna OU id de um card sob o ponteiro (resolvido via ``resolveDropColumn``). */
  overColumn: string | null;
  tasks: TaskCard[];
  actor?: string | null;
  updateTaskStatus: (
    taskId: string,
    payload: {
      expected_version: number;
      new_status: TaskCardStatus;
      actor?: string | null;
    },
  ) => Promise<UpdateStatusResult>;
  updateTask?: (
    taskId: string,
    payload: TaskUpdate,
  ) => Promise<{ conflict: boolean; task?: TaskCard; current_version?: number }>;
  claimTask?: (
    taskId: string,
    claimant: string,
  ) => Promise<{
    claimed: boolean;
    current_assignee?: string | null;
    version?: number;
  }>;
  releaseTask?: (
    taskId: string,
    body?: { actor?: string; reason?: string },
  ) => Promise<unknown>;
}): Promise<CardDropOutcome> {
  const {
    activeId,
    overColumn: overId,
    tasks,
    actor,
    updateTaskStatus,
    updateTask,
    claimTask,
    releaseTask,
  } = params;

  const overTaskId =
    overId && !isTaskColumn(overId) ? overId : null;
  const overColumn = resolveDropColumn(overId, tasks);
  if (!overColumn) {
    return { moved: false, conflict: false };
  }
  const task = tasks.find((t) => t.id === activeId);
  if (!task) {
    return { moved: false, conflict: false };
  }

  const columnPeers = tasks.filter((t) => t.status === overColumn);
  const nextPosition = computeInsertPosition(columnPeers, activeId, overTaskId);

  // Reordenação na mesma coluna (precisa over em outro card).
  if (task.status === overColumn) {
    if (!overTaskId || overTaskId === activeId || !updateTask) {
      return { moved: false, conflict: false, task };
    }
    const res = await updateTask(task.id, {
      expected_version: task.version,
      position: nextPosition,
    });
    return {
      moved: true,
      conflict: res.conflict,
      task: res.task ?? task,
      targetStatus: overColumn,
      position: nextPosition,
      result: res.conflict
        ? { conflict: true, current_version: res.current_version }
        : { conflict: false, task: res.task },
    };
  }

  let version = task.version;

  // Entrar em em_andamento exige claim (não PATCH de status).
  if (overColumn === "em_andamento" && task.status === "tasks") {
    if (!claimTask || !actor) {
      return { moved: false, conflict: false, task };
    }
    const res = await claimTask(task.id, actor);
    if (!res.claimed) {
      return {
        moved: true,
        conflict: true,
        claimedDenied: true,
        currentAssignee: res.current_assignee,
        task,
        targetStatus: overColumn,
      };
    }
    version = res.version ?? version + 1;
  } else if (overColumn === "tasks") {
    // Voltar ao backlog exige release.
    if (!releaseTask) {
      return { moved: false, conflict: false, task };
    }
    await releaseTask(task.id, { actor: actor ?? undefined, reason: "drag to backlog" });
    version = version + 1;
  } else {
    const result = await updateTaskStatus(task.id, {
      expected_version: version,
      new_status: overColumn,
      actor,
    });
    if (result.conflict) {
      return {
        moved: true,
        conflict: true,
        task,
        targetStatus: overColumn,
        result,
      };
    }
    version = result.task?.version ?? version + 1;
  }

  if (updateTask) {
    const posRes = await updateTask(task.id, {
      expected_version: version,
      position: nextPosition,
    });
    if (posRes.conflict) {
      return {
        moved: true,
        conflict: true,
        task,
        targetStatus: overColumn,
        position: nextPosition,
        result: {
          conflict: true,
          current_version: posRes.current_version,
        },
      };
    }
    return {
      moved: true,
      conflict: false,
      task: posRes.task ?? task,
      targetStatus: overColumn,
      position: nextPosition,
      result: { conflict: false, task: posRes.task },
    };
  }

  return {
    moved: true,
    conflict: false,
    task,
    targetStatus: overColumn,
    position: nextPosition,
    result: { conflict: false },
  };
}

export { sortTasksByPosition };
