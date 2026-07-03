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
