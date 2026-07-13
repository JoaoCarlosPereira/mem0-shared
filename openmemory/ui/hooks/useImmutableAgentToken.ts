"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";

import { useApiSessionReady } from "@/hooks/useApiSessionReady";
import { getApiAccessToken } from "@/lib/api-client";

/**
 * Carrega o token de agente imutável (ADR-008) somente após a sessão da UI
 * estar pronta — evita corrida com o AuthBridge no 2º login (redirect direto
 * ao painel sem passar pelo onboarding).
 */
export function useImmutableAgentToken() {
  const { status } = useSession();
  const apiSessionReady = useApiSessionReady();
  const { getOrCreateToken } = useAgentTokenApi();
  const [tokenInfo, setTokenInfo] = useState<AgentToken | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  const apiAccessToken = apiSessionReady ? getApiAccessToken() : null;

  useEffect(() => {
    if (status === "loading") {
      return;
    }

    if (status !== "authenticated" || !apiSessionReady || !apiAccessToken) {
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(false);

    getOrCreateToken(apiAccessToken)
      .then((data) => {
        if (!cancelled) setTokenInfo(data);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status, apiSessionReady, apiAccessToken, getOrCreateToken]);

  return {
    rawToken: tokenInfo?.token ?? null,
    tokenInfo,
    error,
    loading,
  };
}

export default useImmutableAgentToken;
