import { formatDateOnly } from "@/lib/datetime";

const capitalize = (str: string) => {
  if (!str) return "";
  if (str.length <= 1) return str.toUpperCase();
  return str.toUpperCase()[0] + str.slice(1);
};

/** ISO sem fuso (ex.: PostgreSQL UTC via isoformat()) — tratar como UTC. */
const NAIVE_ISO_RE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/;

function parseIsoString(value: string): Date | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  if (/[Zz]$/.test(trimmed) || /[+-]\d{2}:\d{2}$/.test(trimmed)) {
    const parsed = new Date(trimmed);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  if (NAIVE_ISO_RE.test(trimmed)) {
    const normalized = trimmed.includes(" ") ? trimmed.replace(" ", "T") : trimmed;
    const parsed = new Date(`${normalized}Z`);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }
  const parsed = new Date(trimmed);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

/** Normaliza epoch em segundos, milissegundos ou ISO string para Date. */
function toDate(value: number | string): Date | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "string") {
    return parseIsoString(value);
  }
  if (!Number.isFinite(value) || value <= 0) {
    return null;
  }
  // Valores > 1e12 são milissegundos (ex.: Date.getTime()).
  if (value > 1e12) {
    return new Date(value);
  }
  // Valores menores são segundos Unix (ex.: API SQL/Qdrant).
  return new Date(value * 1000);
}

function formatDate(timestamp: number | string) {
  const date = toDate(timestamp);
  if (!date) {
    return "—";
  }

  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 0) {
    return formatDateOnly(date);
  }

  if (diffInSeconds < 60) {
    return "Agora";
  }
  if (diffInSeconds < 3600) {
    const minutes = Math.floor(diffInSeconds / 60);
    return `há ${minutes} ${minutes === 1 ? "minuto" : "minutos"}`;
  }
  if (diffInSeconds < 86400) {
    const hours = Math.floor(diffInSeconds / 3600);
    return `há ${hours} ${hours === 1 ? "hora" : "horas"}`;
  }
  if (diffInSeconds < 86400 * 30) {
    const days = Math.floor(diffInSeconds / 86400);
    return `há ${days} ${days === 1 ? "dia" : "dias"}`;
  }

  return formatDateOnly(date);
}

export { capitalize, formatDate, toDate };
