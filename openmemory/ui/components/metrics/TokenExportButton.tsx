"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { useMetricsApi } from "@/hooks/useMetricsApi";
import { MetricsFilters } from "@/types/metrics";

interface TokenExportButtonProps {
  filters: MetricsFilters;
}

/** Exporta em CSV os dados de consumo com os filtros atuais (task_05). */
export function TokenExportButton({ filters }: TokenExportButtonProps) {
  const { exportCsv, error } = useMetricsApi();
  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportCsv(filters);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-6">
      <h2 className="text-sm font-semibold text-zinc-200">Exportar CSV</h2>
      <p className="mt-1 text-sm text-zinc-400">
        Gera um arquivo CSV com todas as colunas de consumo (tokens, operação,
        agente, usuário, projeto, modelo, duração) respeitando os filtros
        aplicados acima. Valores em tokens — não em custo monetário.
      </p>
      <button
        type="button"
        disabled={exporting}
        onClick={() => void handleExport()}
        className="mt-4 inline-flex items-center gap-2 rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:opacity-50"
      >
        <Download className="h-4 w-4" />
        {exporting ? "Exportando…" : "Exportar CSV"}
      </button>
      {error ? <p className="mt-3 text-sm text-red-400">{error}</p> : null}
    </div>
  );
}
