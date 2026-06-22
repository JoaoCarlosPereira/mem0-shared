const capitalize = (str: string) => {
  if (!str) return "";
  if (str.length <= 1) return str.toUpperCase();
  return str.toUpperCase()[0] + str.slice(1);
};

/** Normaliza epoch em segundos, milissegundos ou ISO string para Date. */
function toDate(value: number | string): Date | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value === "string") {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
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
    return date.toLocaleDateString("pt-BR", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
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

  return date.toLocaleDateString("pt-BR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export { capitalize, formatDate, toDate };
