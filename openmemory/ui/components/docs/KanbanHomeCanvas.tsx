"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { getApiUrl } from "@/lib/api-url";
import { useApiSessionReady } from "@/hooks/useApiSessionReady";

export type KanbanHomeEmbedInfo = {
  embed_url: string;
  access_token: string;
};

type Props = {
  reloadToken?: number;
};

/**
 * Home Kanban (ADR-008): SPA same-origin sob /planka, full-bleed na aba Kanban.
 * Usa axios (Bearer da AuthBridge) — fetch+credentials sozinho não envia o JWT.
 */
export function KanbanHomeCanvas({ reloadToken = 0 }: Props) {
  const apiSessionReady = useApiSessionReady();
  const [info, setInfo] = useState<KanbanHomeEmbedInfo | null>(null);
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
      const res = await axios.get<KanbanHomeEmbedInfo>(
        `${getApiUrl()}/api/v1/specs/kanban-home`,
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
          "Falha ao carregar Kanban",
      );
    } finally {
      setLoading(false);
    }
  }, [apiSessionReady]);

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
        className="flex min-h-0 flex-1 items-center justify-center bg-card/40 text-sm text-muted-foreground"
        data-testid="kanban-home-loading"
      >
        Carregando Kanban…
      </div>
    );
  }

  if (error || !src) {
    return (
      <div
        className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 bg-card/40 p-6 text-center"
        data-testid="kanban-home-error"
      >
        <p className="text-sm text-destructive" role="alert">
          {error || "Kanban indisponível"}
        </p>
        <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
          Tentar de novo
        </Button>
      </div>
    );
  }

  return (
    <iframe
      title="Kanban"
      src={src}
      className="min-h-0 w-full flex-1 border-0 bg-background"
      data-testid="kanban-home-canvas"
      allow="clipboard-read; clipboard-write"
    />
  );
}

export default KanbanHomeCanvas;
