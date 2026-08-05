/**
 * Reverse proxy same-origin para o sidecar PLANKA (Kanban, ADR-007/ADR-008).
 *
 * Diferente de /api-proxy e /registry-api (APIs JSON puras), o PLANKA é uma
 * SPA completa: serve HTML/JS/CSS/imagens + API REST + WebSocket (Socket.IO)
 * todos sob o mesmo prefixo /planka. Esse proxy cobre HTTP; o upgrade de
 * WebSocket não é possível num Route Handler (roda por-requisição, sem acesso
 * ao socket cru) — o cliente Socket.IO cai automaticamente para polling
 * HTTP (comportamento padrão do engine.io), então o board funciona, só sem
 * push instantâneo de mudanças de outros usuários (atualiza no próximo poll).
 *
 * PLANKA_PUBLIC_URL do sidecar já é fixado em "/planka" (ver
 * ensure_update_ops_env em install.py) — os links/assets que o próprio PLANKA
 * gera já assumem esse prefixo relativo, então repassar bytes sem reescrever
 * HTML funciona em qualquer origem (porta 3000 direta, domínio HTTPS, etc.).
 */
export function plankaInternalBase(): string {
  return (
    process.env.PLANKA_INTERNAL_URL ||
    process.env.PLANKA_BASE_URL ||
    "http://planka:1337"
  ).replace(/\/$/, "");
}

/**
 * Reescreve Location de redirects do PLANKA (Docker-internal) para
 * same-origin /planka — mesmo raciocínio de rewriteUpstreamRedirectLocation
 * (api-proxy) e rewriteRegistryRedirectLocation (registry-api).
 */
export function rewritePlankaRedirectLocation(
  location: string,
  internalBase: string,
): string {
  if (!location) {
    return location;
  }

  const base = internalBase.replace(/\/$/, "");
  if (location.startsWith(base)) {
    return `/planka${location.slice(base.length)}`;
  }

  try {
    const parsed = new URL(location);
    const internal = new URL(base.includes("://") ? base : `http://${base}`);
    if (parsed.host === internal.host) {
      return `/planka${parsed.pathname}${parsed.search}${parsed.hash}`;
    }
  } catch {
    if (location.startsWith("/") && !location.startsWith("/planka")) {
      return `/planka${location}`;
    }
  }

  return location;
}
