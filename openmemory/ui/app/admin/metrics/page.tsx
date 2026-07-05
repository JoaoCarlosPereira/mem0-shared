"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3 } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TokenDetailTable } from "@/components/metrics/TokenDetailTable";
import { TokenExportButton } from "@/components/metrics/TokenExportButton";
import { TokenFilters } from "@/components/metrics/TokenFilters";
import { TokenSummaryChart } from "@/components/metrics/TokenSummaryChart";
import { useMetricsApi } from "@/hooks/useMetricsApi";
import { MetricsFilters } from "@/types/metrics";

/** Últimos 30 dias como período padrão (o start é obrigatório na API). */
function defaultFilters(): MetricsFilters {
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
  return {
    start: `${start.toISOString().slice(0, 10)}T00:00:00`,
    end: undefined,
    granularity: "project",
  };
}

export default function MetricsPage() {
  const { summary, loading, error, fetchSummary } = useMetricsApi();
  const [filters, setFilters] = useState<MetricsFilters>(() => defaultFilters());

  useEffect(() => {
    void fetchSummary(filters);
  }, [fetchSummary, filters]);

  const summaryBody = useMemo(() => {
    if (error && !summary) {
      return (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-6">
          <p className="mb-3 text-sm text-red-400">{error}</p>
          <button
            type="button"
            onClick={() => void fetchSummary(filters)}
            className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 hover:bg-zinc-700"
          >
            Tentar novamente
          </button>
        </div>
      );
    }
    if (!summary) {
      return (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full rounded-lg" />
            ))}
          </div>
          <Skeleton className="h-72 w-full rounded-lg" />
          {loading ? (
            <p className="text-xs text-zinc-500">Carregando métricas…</p>
          ) : null}
        </div>
      );
    }
    return <TokenSummaryChart data={summary.data} />;
  }, [error, fetchSummary, filters, loading, summary]);

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={BarChart3}
        title="Métricas de Tokens"
        description="Consumo de tokens LLM por projeto, agente, usuário e modelo — embeddings locais não entram na contagem."
      />
      <div className="space-y-4">
        <TokenFilters filters={filters} onChange={setFilters} />
        <Tabs defaultValue="tokens">
          <TabsList>
            <TabsTrigger value="tokens">Tokens</TabsTrigger>
            <TabsTrigger value="details">Detalhes</TabsTrigger>
            <TabsTrigger value="export">Exportar</TabsTrigger>
          </TabsList>
          <TabsContent value="tokens" className="mt-4">
            {summaryBody}
          </TabsContent>
          <TabsContent value="details" className="mt-4">
            <TokenDetailTable filters={filters} />
          </TabsContent>
          <TabsContent value="export" className="mt-4">
            <TokenExportButton filters={filters} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
