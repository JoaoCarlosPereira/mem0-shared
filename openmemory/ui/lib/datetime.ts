import { toDate } from "@/lib/helpers";

/** Fuso horário padrão exibido na UI (Brasília, UTC−3). */
export const BRASILIA_TIMEZONE = "America/Sao_Paulo";

type DateInput = string | number | Date | null | undefined;

function resolveDate(value: DateInput): Date | null {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (value === null || value === undefined || value === "") {
    return null;
  }
  return toDate(value);
}

function formatParts(
  date: Date,
  options: Intl.DateTimeFormatOptions,
): Intl.DateTimeFormatPart[] {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: BRASILIA_TIMEZONE,
    ...options,
  }).formatToParts(date);
}

function part(
  parts: Intl.DateTimeFormatPart[],
  type: Intl.DateTimeFormatPartTypes,
): string {
  return parts.find((p) => p.type === type)?.value ?? "";
}

/** dd/MM/yyyy HH:mm:ss em horário de Brasília. */
export function formatDateTimeFull(value: DateInput): string {
  const date = resolveDate(value);
  if (!date) return "—";
  const p = formatParts(date, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  return `${part(p, "day")}/${part(p, "month")}/${part(p, "year")} ${part(p, "hour")}:${part(p, "minute")}:${part(p, "second")}`;
}

/** dd/MM/yyyy HH:mm em horário de Brasília. */
export function formatDateTimeShort(value: DateInput): string {
  const date = resolveDate(value);
  if (!date) return "—";
  const p = formatParts(date, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${part(p, "day")}/${part(p, "month")}/${part(p, "year")} ${part(p, "hour")}:${part(p, "minute")}`;
}

/** Data legível (ex.: 20 de jun. de 2026) em horário de Brasília. */
export function formatDateOnly(value: DateInput): string {
  const date = resolveDate(value);
  if (!date) return "—";
  return date.toLocaleDateString("pt-BR", {
    timeZone: BRASILIA_TIMEZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Data/hora legível (ex.: 20 de jun. de 2026, 07:00) em horário de Brasília. */
export function formatDateTime(value: DateInput): string {
  const date = resolveDate(value);
  if (!date) return "—";
  return date.toLocaleString("pt-BR", {
    timeZone: BRASILIA_TIMEZONE,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "numeric",
  });
}
