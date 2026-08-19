"use client";

import { useEffect, useMemo, useState } from "react";
import { BarChart3, Activity, Zap, Cpu, Layers, Search } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TokenDetailTable } from "@/components/metrics/TokenDetailTable";
import { TokenExportButton } from "@/components/metrics/TokenExportButton";
import { TokenFilters } from "@/components/metrics/TokenFilters";
import { TokenSummaryChart } from "@/components/metrics/TokenSummaryChart";
import { useMetricsApi } from "@/hooks/useMetricsApi";
import { MetricsFilters } from "@/types/metrics";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

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

  const summaryData = useMemo(() => {
    if (error && !summary) {
      return {
        error: error,
        isError: true,
      };
    }
    if (!summary) {
      return {
        isLoading: true,
      };
    }
    return {
      summary,
      isError: false,
      isLoading: false,
    };
  }, [error, fetchSummary, filters, loading, summary]);

  return (
    <div className="max-w-[1600px] mx-auto space-y-6 pb-12">
      <PageHeader
        className="mb-2"
        icon={BarChart3}
        title="Análise de Consumo"
        description="Monitoramento detalhado de tokens, operações e performance de modelos."
      />

      <div className="space-y-6">
        <TokenFilters filters={filters} onChange={setFilters} />

        {/* Summary / KPI Section - Automatically populated by TokenSummaryChart's internal tiles */}
        
        <Tabs defaultValue="tokens" className="w-full">
          <div className="flex items-center justify-between mb-4">
            <TabsList className="bg-zinc-900/50 border border-zinc-800 p-1">
              <TabsTrigger value="tokens" className="px-6">Tendências de Tokens</TabsTrigger>
              <TabsTrigger value="details" className="px-6">Log de Operações</TabsTrigger>
              <TabsTrigger value="export" className="px-6">Exportação</TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="tokens" className="space-y-6 outline-none">
            {summaryData.isError ? (
              <Card className="border-red-900/50 bg-red-950/20">
                <CardContent className="p-6 text-center">
                  <p className="text-red-400 mb-4">{summaryData.error}</p>
                  <button
                    type="button"
                    onClick={() => void fetchSummary(filters)}
                    className="rounded-md bg-red-500/20 px-4 py-2 text-sm font-medium text-red-200 hover:bg-red-500/30 transition-colors"
                  >
                    Tentar novamente
                  </button>
                </CardContent>
              </Card>
            ) : summaryData.isLoading ? (
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-24 w-full rounded-xl" />
                  ))}
                </div>
                <Skeleton className="h-[450px] w-full rounded-xl" />
              </div>
            ) : (
              <TokenSummaryChart data={summaryData.summary!.data} />
            )}
          </TabsContent>

          <TabsContent value="details" className="outline-none">
            <TokenDetailTable filters={filters} />
          </TabsContent>

          <TabsContent value="export" className="outline-none">
            <div className="flex justify-center py-12">
              <TokenExportButton filters={filters} />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
