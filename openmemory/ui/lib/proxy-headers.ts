/**
 * Sanitização de headers do reverse proxy /api-proxy.
 *
 * Remove headers hop-by-hop (RFC 7230 §6.1) e os que o fetch/undici recalcula
 * antes de repassar a requisição do cliente para a API interna. Sem isso, com
 * a UI atrás de um proxy (nginx/Traefik), headers normalizados (Connection,
 * Transfer-Encoding, Content-Length) fazem o fetch do upstream lançar → 500.
 */
export const HOP_BY_HOP_HEADERS = [
  "host",
  "connection",
  "keep-alive",
  "proxy-connection",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "content-length",
];

export function sanitizeUpstreamHeaders(input: Headers): Headers {
  const out = new Headers(input);
  for (const name of HOP_BY_HOP_HEADERS) out.delete(name);
  return out;
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

/**
 * Em UI legado (sem sessão Google), mutações ``/admin/*`` exigem
 * ``X-Admin-Token`` / sessão JWT. O browser não deve receber ``ADMIN_TOKEN``;
 * o proxy injeta o segredo server-side quando a chamada chega sem credencial.
 *
 * Não sobrescreve Authorization / X-Admin-Token já enviados (sessão Google ou
 * token explícito do operador).
 */
export function applyLegacyAdminToken(
  headers: Headers,
  options: {
    method: string;
    pathSegments: string[];
    adminToken?: string;
  },
): Headers {
  const token = (options.adminToken ?? process.env.ADMIN_TOKEN ?? "").trim();
  if (!token) return headers;
  if (!MUTATING_METHODS.has(options.method.toUpperCase())) return headers;
  if (options.pathSegments[0] !== "admin") return headers;
  if (headers.get("x-admin-token")?.trim()) return headers;
  if (headers.get("authorization")?.trim()) return headers;

  const out = new Headers(headers);
  out.set("x-admin-token", token);
  return out;
}

/**
 * Rewrite upstream redirect targets (Docker-internal API URL) to same-origin
 * ``/api-proxy`` so the browser never follows ``openmemory-mcp:8765``.
 */
export function rewriteUpstreamRedirectLocation(
  location: string,
  internalBase: string,
): string {
  const base = internalBase.replace(/\/$/, "");
  if (!location) {
    return location;
  }

  if (location.startsWith(base)) {
    return `/api-proxy${location.slice(base.length)}`;
  }

  try {
    const parsed = new URL(location);
    const internal = new URL(base.includes("://") ? base : `http://${base}`);
    if (parsed.host === internal.host) {
      return `/api-proxy${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    if (location.startsWith("/")) {
      return `/api-proxy${location}`;
    }
  }

  return location;
}
