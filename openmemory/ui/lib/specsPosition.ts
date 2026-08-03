/** Ordenação gap-based de cards Spec (espelha convenção PLANKA / Spec position). */

import type { TaskCard } from "@/types/specs";

export const POSITION_STEP = 65536;

export function taskPosition(task: Pick<TaskCard, "position">): number {
  return typeof task.position === "number" && Number.isFinite(task.position)
    ? task.position
    : POSITION_STEP;
}

export function sortTasksByPosition(tasks: TaskCard[]): TaskCard[] {
  return [...tasks].sort((a, b) => {
    const diff = taskPosition(a) - taskPosition(b);
    if (diff !== 0) return diff;
    return a.id.localeCompare(b.id);
  });
}

/**
 * Calcula ``position`` ao soltar ``activeId`` na coluna, opcionalmente antes
 * do card ``overTaskId`` (drop sobre outro card). Sem over → append no fim.
 */
export function computeInsertPosition(
  columnTasks: TaskCard[],
  activeId: string,
  overTaskId: string | null,
): number {
  const others = sortTasksByPosition(
    columnTasks.filter((t) => t.id !== activeId),
  );
  if (others.length === 0) return POSITION_STEP;

  if (!overTaskId) {
    return taskPosition(others[others.length - 1]) + POSITION_STEP;
  }

  const idx = others.findIndex((t) => t.id === overTaskId);
  if (idx < 0) {
    return taskPosition(others[others.length - 1]) + POSITION_STEP;
  }

  const overPos = taskPosition(others[idx]);
  if (idx === 0) {
    return overPos / 2;
  }
  const prevPos = taskPosition(others[idx - 1]);
  return (prevPos + overPos) / 2;
}
