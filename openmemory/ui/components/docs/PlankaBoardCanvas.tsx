"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { getApiUrl } from "@/lib/api-url";
import { useApiSessionReady } from "@/hooks/useApiSessionReady";

export type PlankaEmbedInfo = {
  workspace_id: string;
  board_id: string;
  project_id?: string | null;
  embed_url: string;
  access_token: string;
};

type Props = {
  workspaceId: string;
  /** Disparado após criar task via Spec (iframe deve recarregar). */
  reloadToken?: number;
};

/**
 * Canvas PLANKA (ADR-007): SPA same-origin sob /planka, isolado do React 19.
 * Spec SoT permanece; o iframe consome JWT Mem0 via query mem0_token.
 * Usa axios (Bearer AuthBridge) para o embed herdar a pessoa logada.
 */
export function PlankaBoardCanvas({ workspaceId, reloadToken = 0 }: Props) {
  const apiSessionReady = useApiSessionReady();
  const [info, setInfo] = useState<PlankaEmbedInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    if (!apiSessionReady) {
      setLoading(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<PlankaEmbedInfo>(
        `${getApiUrl()}/api/v1/specs/workspaces/${workspaceId}/planka-embed`,
      );
      setInfo(res.data);
    } catch (err: unknown) {
      setInfo(null);
      const detail =
        axios.isAxiosError(err)
          ? err.response?.data?.detail?.detail ||
            err.response?.data?.detail ||
            err.message
          : null;
      setError(
        (typeof detail === "string" && detail) ||
          "Falha ao carregar quadro PLANKA",
      );
    } finally {
      setLoading(false);
    }
  }, [workspaceId, apiSessionReady]);

  useEffect(() => {
    void load();
  }, [load, reloadToken]);

  const src = useMemo(() => {
    if (!info?.embed_url || !info.access_token) return null;
    const url = new URL(info.embed_url, window.location.origin);
    url.searchParams.set("mem0_token", info.access_token);
    url.searchParams.set("embed", "1");
    return url.toString();
  }, [info]);

  if (!apiSessionReady || loading) {
    return (
      <div
        className="flex min-h-0 flex-1 items-center justify-center rounded-md border border-border bg-card/40 text-sm text-muted-foreground"
        data-testid="planka-canvas-loading"
      >
        Carregando quadro PLANKA…
      </div>
    );
  }

  if (error || !src) {
    return (
      <div
        className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 rounded-md border border-border bg-card/40 p-6 text-center"
        data-testid="planka-canvas-error"
      >
        <p className="text-sm text-destructive" role="alert">
          {error || "Embed PLANKA indisponível"}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
          Tentar de novo
        </Button>
      </div>
    );
  }

  return (
    <iframe
      title="Quadro PLANKA"
      src={src}
      className="min-h-0 w-full flex-1 rounded-md border border-border bg-background"
      data-testid="planka-board-canvas"
      allow="clipboard-read; clipboard-write"
    />
  );
}

export default PlankaBoardCanvas;
