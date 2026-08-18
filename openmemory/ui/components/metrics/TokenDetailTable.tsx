"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowDown, ArrowUp, CheckCircle2, XCircle } from "lucide-react";
import { useMetricsApi } from "@/hooks/useMetricsApi";
import { MetricsFilters, SortBy, SortOrder } from "@/types/metrics";
import { Skeleton } from "@/components/ui/skeleton";
import { Card } from "@/components/ui/card";

interface TokenDetailTableProps {
  filters: MetricsFilters;
}

const PAGE_SIZE = 50;

const SORTABLE: { key: SortBy; label: string }[] = [
  { key: "created_at", label: "Data" },
  { key: "input_tokens", label: "Entrada" },
  { key: "output_tokens", label: "Saída" },
  { key: "total_tokens", label: "Total" },
  { key: "duration_ms", label: "Duração (ms)" },
];

const numberFmt = new Intl.NumberFormat("pt-BR");

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  });
}

/** Tabela detalhada de consumo com design refinado e modernizado. */
export function TokenDetailTable({ filters }: TokenDetailTableProps) {
  const { details, loading, error, fetchDetails } = useMetricsApi();
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const load = useCallback(
    (targetPage: number, by: SortBy, order: SortOrder) => {
      void fetchDetails(filters, {
        page: targetPage,
        pageSize: PAGE_SIZE,
        sortBy: by,
        sortOrder: order,
      });
    },
    [fetchDetails, filters],
  );

  useEffect(() => {
    setPage(1);
    load(1, sortBy, sortOrder);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const toggleSort = (key: SortBy) => {
    const order: SortOrder =
      sortBy === key && sortOrder === "desc" ? "asc" : "desc";
    setSortBy(key);
    setSortOrder(order);
    setPage(1);
    load(1, key, order);
  };

  const goTo = (targetPage: number) => {
    setPage(targetPage);
    load(targetPage, sortBy, sortOrder);
  };

  if (error && !details) {
    return (
      <Card className="border-red-900/50 bg-red-950/20 p-6 text-center">
        <p className="mb-4 text-sm text-red-400">{error}</p>
        <button
          type="button"
          onClick={() => load(page, sortBy, sortOrder)}
          className="rounded-md bg-red-500/20 px-4 py-2 text-sm font-medium text-red-200 hover:bg-red-500/30 transition-colors"
        >
          Tentar novamente
        </button>
      </Card>
    );
  }

  if (!details) {
    return <Skeleton className="h-96 w-full rounded-xl" />;
  }

  const totalPages = Math.max(1, Math.ceil(details.total / details.page_size));

  const sortIndicator = (key: SortBy) =>
    sortBy === key ? (
      sortOrder === "desc" ? (
        <ArrowDown className="ml-1 h-3 w-3" />
      ) : (
        <ArrowUp className="ml-1 h-3 w-3" />
      )
    ) : null;

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/20">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/50 text-xs font-medium uppercase tracking-wider text-zinc-500">
              <tr>
                <th className="px-4 py-3">
                  <button
                    type="button"
                    className="flex items-center hover:text-zinc-200 transition-colors"
                    onClick={() => toggleSort("created_at")}
                  >
                    Data {sortIndicator("created_at")}
                  </button>
                </th>
                <th className="px-4 py-3">Projeto</th>
                <th className="px-4 py-3">Agente</th>
                <th className="px-4 py-3">Usuário</th>
                <th className="px-4 py-3">Operação</th>
                <th className="px-4 py-3">Modelo</th>
                {SORTABLE.slice(1).map((col) => (
                  <th key={col.key} className="px-4 py-3 text-right">
                    <button
                      type="button"
                      className="flex items-center justify-end w-full hover:text-zinc-200 transition-colors"
                      onClick={() => toggleSort(col.key)}
                    >
                      {col.label} {sortIndicator(col.key)}
                    </button>
                  </th>
                ))}
                <th className="px-4 py-3 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50 text-zinc-300">
              {details.data.length === 0 ? (
                <tr>
                  <td colSpan={12} className="px-4 py-12 text-center text-zinc-500 italic">
                    Sem registros para os filtros aplicados.
                  </td>
                </tr>
              ) : (
                details.data.map((row) => (
                  <tr key={row.id} className="group hover:bg-zinc-800/30 transition-colors">
                    <td className="whitespace-nowrap px-4 py-3 text-zinc-400">
                      {formatDate(row.created_at)}
                    </td>
                    <td className="px-4 py-3 font-medium text-zinc-200">{row.project}</td>
                    <td className="px-4 py-3">{row.agent}</td>
                    <td className="px-4 py-3 text-zinc-400">{row.user_id}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-[10px] font-medium uppercase tracking-tight text-zinc-400">
                        {row.operation_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-400">{row.model}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-zinc-200">
                      {numberFmt.format(row.input_tokens)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-zinc-200">
                      {numberFmt.format(row.output_tokens)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-semibold text-zinc-100">
                      {numberFmt.format(row.total_tokens)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-zinc-400">
                      {row.duration_ms != null
                        ? numberFmt.format(row.duration_ms)
                        : "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-center">
                        {row.success ? (
                          <div className="flex items-center gap-1.5 text-emerald-400" title="Sucesso">
                            <CheckCircle2 className="h-4 w-4" />
                            <span className="text-xs font-medium">ok</span>
                          </div>
                        ) : (
                          <div className="flex items-center gap-1.5 text-red-400" title={row.error ?? "Erro desconhecido"}>
                            <XCircle className="h-4 w-4" />
                            <span className="text-xs font-medium">erro</span>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="flex items-center justify-between px-1">
        <div className="text-sm text-zinc-500">
          <span className="font-medium text-zinc-300">{numberFmt.format(details.total)}</span> registros encontrados — página {details.page} de {totalPages}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => goTo(page - 1)}
            className="rounded-md border border-zinc-800 bg-zinc-900/50 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Anterior
          </button>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => goTo(page + 1)}
            className="rounded-md border border-zinc-800 bg-zinc-900/50 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-800 hover:text-white transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          >
            Próxima
          </button>
        </div>
      </div>
    </div>
  );
}
