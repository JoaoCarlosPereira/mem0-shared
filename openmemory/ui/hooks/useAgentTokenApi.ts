import { useCallback } from "react";
import axios from "axios";
import { getApiUrl } from "@/lib/api-url";

export interface AgentToken {
  /** Valor em claro — imutável e permanentemente exibível (ADR-008). */
  token: string | null;
  prefix: string;
  created_at: string | null;
  last_used_at: string | null;
}

/**
 * Hook do token de agente imutável (ADR-008): get-or-create idempotente.
 * Padrão `useGroupsApi`; o Bearer da sessão vai pelo interceptor global.
 */
export const useAgentTokenApi = () => {
  /** Cria na primeira chamada; depois devolve sempre o mesmo token. */
  const getOrCreateToken = useCallback(async (): Promise<AgentToken> => {
    const res = await axios.post<AgentToken>(`${getApiUrl()}/api/v1/agent-token`);
    return res.data;
  }, []);

  /** Token atual (com o valor) ou null se nunca gerado. */
  const fetchToken = useCallback(async (): Promise<AgentToken | null> => {
    try {
      const res = await axios.get<AgentToken>(`${getApiUrl()}/api/v1/agent-token`);
      return res.data;
    } catch (err: any) {
      if (err?.response?.status === 404) return null;
      throw err;
    }
  }, []);

  return { getOrCreateToken, fetchToken };
};

export default useAgentTokenApi;
