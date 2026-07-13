import axios from "axios";

/** Extrai mensagem legível de erros FastAPI/axios. */
export function parseApiError(
  err: unknown,
  fallback = "Falha na requisição",
): string {
  if (axios.isAxiosError(err)) {
    if (err.response?.status === 401) {
      return "Sessão expirada — faça login novamente com sua conta Google.";
    }
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      if (
        err.response?.status === 403 &&
        detail.toLowerCase().includes("deletion blocked")
      ) {
        return (
          "Exclusão de memórias desabilitada neste servidor (proteção fail-closed). " +
          "Peça ao administrador para definir MEM0_ALLOW_MEMORY_DELETE=1."
        );
      }
      return detail;
    }
    if (Array.isArray(detail)) {
      return detail.map((d) => d?.msg ?? String(d)).join("; ");
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}
