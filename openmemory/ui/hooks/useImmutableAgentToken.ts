"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";

import {
  useAgentTokenApi,
  type AgentToken,
} from "@/hooks/useAgentTokenApi";

/**
 * Carrega o token de agente imutável (ADR-008) somente após a sessão da UI
 * estar pronta — evita corrida com o AuthBridge no 2º login (redirect direto
 * ao painel sem passar pelo onboarding).
 */
export function useImmutableAgentToken() {
  const { data: session, status } = useSession();
  const { getOrCreateToken } = useAgentTokenApi();
  const [tokenInfo, setTokenInfo] = useState<AgentToken | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  const apiAccessToken = (session as { apiAccessToken?: string | null } | null)
    ?.apiAccessToken;

  useEffect(() => {
    if (status === "loading") {
      return;
    }

    if (status !== "authenticated" || !apiAccessToken) {
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
  }, [status, apiAccessToken, getOrCreateToken]);

  return {
    rawToken: tokenInfo?.token ?? null,
    tokenInfo,
    error,
    loading,
  };
}

export default useImmutableAgentToken;
