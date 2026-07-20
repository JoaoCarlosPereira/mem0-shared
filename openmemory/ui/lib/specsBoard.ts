// Lógica pura do quadro Kanban de specs (task_14). Colunas fixas do sistema
// (ADR-001/ADR-007), sem customização por projeto no MVP. Separada da UI para
// ser testável sem simular drag-and-drop real (impraticável em jsdom).

import type { TaskCard, TaskCardStatus, UpdateStatusResult } from "@/types/specs";

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

export interface CardDropOutcome {
  moved: boolean; // a chamada de atualização foi disparada
  conflict: boolean; // servidor rejeitou por conflito de versão (409)
  task?: TaskCard;
  targetStatus?: TaskCardStatus;
  result?: UpdateStatusResult;
}

/**
 * Decide e efetiva o resultado de soltar um card de task numa coluna.
 *
 * - Ignora drops sem alvo, em card de documento, ou na mesma coluna (moved=false).
 * - Caso contrário chama ``updateTaskStatus`` com o ``expected_version`` atual do
 *   card (concorrência otimista) e propaga o resultado. O chamador (a página)
 *   aplica a UI otimista e reverte quando ``conflict=true``.
 */
export async function handleCardDrop(params: {
  activeId: string;
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
}): Promise<CardDropOutcome> {
  const { activeId, overColumn, tasks, actor, updateTaskStatus } = params;

  if (!overColumn || !isTaskColumn(overColumn)) {
    return { moved: false, conflict: false };
  }
  const task = tasks.find((t) => t.id === activeId);
  if (!task || task.status === overColumn) {
    return { moved: false, conflict: false, task };
  }

  const result = await updateTaskStatus(task.id, {
    expected_version: task.version,
    new_status: overColumn,
    actor,
  });

  return {
    moved: true,
    conflict: result.conflict,
    task,
    targetStatus: overColumn,
    result,
  };
}
