/**
 * Base URL for OpenMemory API calls from the browser.
 *
 * Default ``/api-proxy`` is proxied at runtime to the internal API container,
 * so LAN clients always talk to the same host:port as the UI (no hard-coded IP
 * or localhost in cached JS bundles).
 */
export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "/api-proxy"
).replace(/\/$/, "");

/** Direct API URL for MCP/SSE clients (cannot use the browser proxy). */
export function getMcpBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_MCP_URL) {
    return process.env.NEXT_PUBLIC_MCP_URL.replace(/\/$/, "");
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8765`;
  }
  return API_URL.startsWith("http") ? API_URL : "http://localhost:8765";
}
