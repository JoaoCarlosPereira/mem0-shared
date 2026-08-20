"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useApiSessionReady } from "@/hooks/useApiSessionReady";
import type { MemoryGraphPayload } from "@/components/memory-graph/types";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";

// THREE/WASM só pode rodar no browser — evita crash de SSR.
const MemoryGraphCanvas = dynamic(
  () =>
    import("@/components/memory-graph/MemoryGraphCanvas").then(
      (mod) => ({ default: mod.MemoryGraphCanvas })
    ),
  { ssr: false }
);

/**
 * Seção "Grafo" da página /memories (Tarefa 04).
 * Busca GET /api/v1/memories/graph, monta o MemoryGraphPayload e
 * navega para /memory/{id} no clique do nó.
 */
export function MemoriesGraphSection() {
  const router = useRouter();
  const apiSessionReady = useApiSessionReady();
  const { fetchMemoryGraph } = useMemoriesApi();
  // Reuso do filtro de projeto existente: app selecionado em MemoryFilters.
  const selectedApps = useSelector(
    (state: RootState) => state.filters.apps.selectedApps
  );

  const [payload, setPayload] = useState<MemoryGraphPayload | null>(null);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError, setGraphError] = useState<string | null>(null);

  const selectedApp =
    selectedApps.length === 1 ? selectedApps[0] : undefined;

  useEffect(() => {
    if (!apiSessionReady) return;

    let cancelled = false;

    const loadGraph = async () => {
      setGraphLoading(true);
      setGraphError(null);
      try {
        // Sem filtro => visão global (padrão do PRD); com 1 app => projeto.
        const result = await fetchMemoryGraph(selectedApp);
        if (cancelled) return;

        const nodes = result.nodes.map((n: any) => ({
          id: n.id,
          name: n.name ?? "Sem título",
          group: n.project ?? undefined,
          orphan: n.orphan ?? false,
          created_at: n.created_at,
        }));

        const links = result.links.map((l: any) => ({
          source: l.source,
          target: l.target,
        }));

        setPayload({ meta: {}, nodes, links });
      } catch (err: any) {
        if (cancelled) return;
        setGraphError(err?.response?.data?.detail ?? err?.message ?? "Falha ao carregar grafo");
        setPayload(null);
      } finally {
        if (!cancelled) setGraphLoading(false);
      }
    };

    void loadGraph();
    return () => {
      cancelled = true;
    };
  }, [apiSessionReady, fetchMemoryGraph, selectedApp]);

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      router.push(`/memory/${nodeId}`);
    },
    [router]
  );

  return (
    <MemoryGraphCanvas
      payload={payload}
      loading={graphLoading}
      error={graphError}
      onNodeClick={handleNodeClick}
    />
  );
}

export default MemoriesGraphSection;
