/** Rótulos PT-BR para estados técnicos exibidos na UI. */
import { toDate } from "@/lib/helpers";
export const MEMORY_STATE_LABELS: Record<string, string> = {
  active: "Ativa",
  paused: "Pausada",
  archived: "Arquivada",
  deleted: "Excluída",
};

export const JOB_STATUS_LABELS: Record<string, string> = {
  queued: "Na fila",
  processing: "Processando",
  done: "Concluído",
  skipped: "Ignorado",
  failed: "Falhou",
};

export const APP_STATUS_LABELS: Record<string, string> = {
  active: "Ativo",
  inactive: "Inativo",
};

export function memoryStateLabel(state: string): string {
  return MEMORY_STATE_LABELS[state] ?? state;
}

export function jobStatusLabel(status: string): string {
  return JOB_STATUS_LABELS[status] ?? status;
}

export function appStatusLabel(active: boolean): string {
  return active ? APP_STATUS_LABELS.active : APP_STATUS_LABELS.inactive;
}

/** Formata data/hora no padrão brasileiro (ISO, segundos ou milissegundos). */
export function formatDateTime(value: string | number | Date): string {
  const date = value instanceof Date ? value : toDate(value);
  if (!date) return "—";
  return date.toLocaleString("pt-BR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "numeric",
  });
}
