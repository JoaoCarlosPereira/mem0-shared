/**
 * Base URL for OpenMemory API calls from the browser.
 *
 * In the browser we always use the same-origin relative ``/api-proxy`` path so
 * LAN clients never depend on a hard-coded IP or ``localhost`` baked into the
 * JS bundle (avoids stale-cache ERR_CONNECTION_REFUSED).
 */
const ENV_URL = process.env.NEXT_PUBLIC_API_URL;

function envOverride(): string | null {
  if (!ENV_URL || ENV_URL === "NEXT_PUBLIC_API_URL" || ENV_URL === "/api-proxy") {
    return null;
  }
  if (ENV_URL.startsWith("http://") || ENV_URL.startsWith("https://")) {
    return ENV_URL.replace(/\/$/, "");
  }
  return null;
}

/** Resolve API base URL at call time (never trust a stale build-time constant). */
export function getApiUrl(): string {
  const override = envOverride();
  if (override) {
    return override;
  }
  if (typeof window !== "undefined") {
    return "/api-proxy";
  }
  return "/api-proxy";
}

/** Direct API URL for MCP/SSE clients (cannot use the browser proxy). */
export function getMcpBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_MCP_URL) {
    return process.env.NEXT_PUBLIC_MCP_URL.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8765`;
  }
  const override = envOverride();
  if (override) {
    return override;
  }
  return "http://localhost:8765";
}

type DiscoveryResponse = {
  base_url?: string;
};

/**
 * Resolve the MCP base URL from the server's /discovery endpoint so install
 * commands always show the memory host's LAN IP, not the UI DNS hostname.
 */
export async function fetchMcpBaseUrl(): Promise<string> {
  const fallback = getMcpBaseUrl();
  try {
    const apiBase = getApiUrl().replace(/\/$/, "");
    const res = await fetch(`${apiBase}/discovery`);
    if (!res.ok) {
      return fallback;
    }
    const data = (await res.json()) as DiscoveryResponse;
    const base = data.base_url?.trim();
    if (base) {
      return base.replace(/\/$/, "");
    }
  } catch {
    // Discovery unavailable — keep synchronous fallback.
  }
  return fallback;
}
