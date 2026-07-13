import axios from "axios";

import { notifySessionExpired } from "@/lib/session-expiry";

const UI_CLIENT = "openmemory-ui";

/**
 * JWT de sessão emitido pela API (feature auth Google, ADR-002). Mantido pelo
 * <AuthBridge/> a partir da sessão NextAuth; anexado como Bearer em todas as
 * chamadas para que o backend identifique a pessoa.
 */
let apiAccessToken: string | null = null;

export function setApiAccessToken(token: string | null) {
  apiAccessToken = token;
}

export function getApiAccessToken(): string | null {
  return apiAccessToken;
}

function tagRequest(config: any) {
  config.headers = config.headers ?? {};
  if (!config.headers["x-client-name"]) {
    config.headers["x-client-name"] = UI_CLIENT;
  }
  if (apiAccessToken && !config.headers["Authorization"]) {
    config.headers["Authorization"] = `Bearer ${apiAccessToken}`;
  }
  return config;
}

const DOCKER_API_HOSTS = /^(openmemory-mcp|openmemory-api|openmemory_mcp)$/i;

/** Force browser calls through /api-proxy (CSP + stale bundle safety). */
function rewriteBrowserApiUrl(url: string): string {
  if (typeof window === "undefined" || !url) {
    return url;
  }
  if (url.startsWith("/api-proxy")) {
    return url;
  }
  try {
    const parsed = new URL(url, window.location.origin);
    if (
      DOCKER_API_HOSTS.test(parsed.hostname) ||
      (parsed.port === "8765" && parsed.origin !== window.location.origin)
    ) {
      return `/api-proxy${parsed.pathname}${parsed.search}`;
    }
  } catch {
    // keep original url
  }
  return url;
}

function proxyGuardRequest(config: any) {
  if (config.url) {
    config.url = rewriteBrowserApiUrl(String(config.url));
  }
  return tagRequest(config);
}

/** Tagged axios instance for new code. (Fallback p/ axios auto-mockado em testes.) */
const createdInstance =
  typeof axios.create === "function"
    ? axios.create({ headers: { "x-client-name": UI_CLIENT } })
    : undefined;
export const apiClient = createdInstance ?? axios;
createdInstance?.interceptors?.request?.use(proxyGuardRequest);

// Existing hooks import bare `axios` — tag those requests too.
axios.interceptors?.request?.use(proxyGuardRequest);

function attachUnauthorizedInterceptor(instance: typeof axios) {
  instance.interceptors?.response?.use(
    (response) => response,
    (error) => {
      if (
        axios.isAxiosError(error) &&
        error.response?.status === 401 &&
        apiAccessToken
      ) {
        setApiAccessToken(null);
        notifySessionExpired();
      }
      return Promise.reject(error);
    },
  );
}

attachUnauthorizedInterceptor(axios);
if (createdInstance) {
  attachUnauthorizedInterceptor(createdInstance);
}
