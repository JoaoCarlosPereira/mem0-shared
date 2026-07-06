/**
 * Base URL for OpenMemory API calls from the browser.
 *
 * In the browser we always use the same-origin relative ``/api-proxy`` path so
 * LAN clients never depend on a hard-coded IP or ``localhost`` baked into the
 * JS bundle (avoids stale-cache ERR_CONNECTION_REFUSED).
 */
/** Read at call time so runtime env / entrypoint sed cannot bake a stale URL. */
function readPublicApiUrl(): string | undefined {
  return process.env.NEXT_PUBLIC_API_URL;
}

/** Docker service names and other hosts the browser cannot resolve. */
const INTERNAL_API_HOSTS = new Set(["openmemory-mcp", "openmemory_mcp"]);

function envOverride(): string | null {
  const envUrl = readPublicApiUrl();
  if (!envUrl || envUrl === "NEXT_PUBLIC_API_URL" || envUrl === "/api-proxy") {
    return null;
  }
  if (envUrl.startsWith("/")) {
    return envUrl.replace(/\/$/, "") || "/api-proxy";
  }
  if (!envUrl.startsWith("http://") && !envUrl.startsWith("https://")) {
    return null;
  }
  const normalized = envUrl.replace(/\/$/, "");
  if (typeof window === "undefined") {
    return normalized;
  }
  try {
    const parsed = new URL(normalized);
    if (INTERNAL_API_HOSTS.has(parsed.hostname)) {
      return null;
    }
    // CSP default-src 'self': only same-origin absolute URLs are allowed.
    if (parsed.origin !== window.location.origin) {
      return null;
    }
    return normalized;
  } catch {
    return null;
  }
}

/** Resolve API base URL at call time (never trust a stale build-time constant). */
export function getApiUrl(): string {
  // Browser: always same-origin proxy — never read NEXT_PUBLIC_* (avoids stale
  // bundles, entrypoint sed, or CSP blocks on Docker hostnames / LAN IPs).
  if (typeof window !== "undefined") {
    return "/api-proxy";
  }
  const override = envOverride();
  if (override) {
    return override;
  }
  return "/api-proxy";
}

/** Hosts/IPs that agents on the LAN cannot use (Docker bridge / internal DNS). */
export function isUnusableMcpAdvertiseUrl(url: string): boolean {
  try {
    const { hostname } = new URL(url);
    if (
      hostname === "openmemory-mcp" ||
      hostname === "openmemory_mcp" ||
      hostname.startsWith("172.17.") ||
      hostname.startsWith("172.18.")
    ) {
      return true;
    }
  } catch {
    return true;
  }
  return false;
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
    if (base && !isUnusableMcpAdvertiseUrl(base)) {
      return base.replace(/\/$/, "");
    }
  } catch {
    // Discovery unavailable — keep synchronous fallback.
  }
  return fallback;
}
