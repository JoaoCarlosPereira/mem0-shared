import axios from "axios";

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

/** Tagged axios instance for new code. (Fallback p/ axios auto-mockado em testes.) */
const createdInstance =
  typeof axios.create === "function"
    ? axios.create({ headers: { "x-client-name": UI_CLIENT } })
    : undefined;
export const apiClient = createdInstance ?? axios;
createdInstance?.interceptors?.request?.use(tagRequest);

// Existing hooks import bare `axios` — tag those requests too.
axios.interceptors?.request?.use(tagRequest);
