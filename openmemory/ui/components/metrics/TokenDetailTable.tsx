"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { useMetricsApi } from "@/hooks/useMetricsApi";
import { MetricsFilters, SortBy, SortOrder } from "@/types/metrics";
import { Skeleton } from "@/components/ui/skeleton";

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
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("pt-BR");
}

/** Tabela detalhada de consumo com paginação e ordenação (task_05). */
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
    // Recarrega quando filtros mudam; sort é tratado no handler do header.
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
      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-6">
        <p className="mb-3 text-sm text-red-400">{error}</p>
        <button
          type="button"
          onClick={() => load(page, sortBy, sortOrder)}
          className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 hover:bg-zinc-700"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  if (!details) {
    return <Skeleton className="h-64 w-full rounded-lg" />;
  }

  const totalPages = Math.max(1, Math.ceil(details.total / details.page_size));

  const sortIndicator = (key: SortBy) =>
    sortBy === key ? (
      sortOrder === "desc" ? (
        <ArrowDown className="inline h-3 w-3" />
      ) : (
        <ArrowUp className="inline h-3 w-3" />
      )
    ) : null;

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-zinc-800">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="bg-zinc-900 text-xs uppercase text-zinc-400">
            <tr>
              <th className="px-3 py-2">
                <button
                  type="button"
                  className="hover:text-zinc-200"
                  onClick={() => toggleSort("created_at")}
                >
                  Data {sortIndicator("created_at")}
                </button>
              </th>
              <th className="px-3 py-2">Projeto</th>
              <th className="px-3 py-2">Agente</th>
              <th className="px-3 py-2">Usuário</th>
              <th className="px-3 py-2">Operação</th>
              <th className="px-3 py-2">Modelo</th>
              {SORTABLE.slice(1).map((col) => (
                <th key={col.key} className="px-3 py-2 text-right">
                  <button
                    type="button"
                    className="hover:text-zinc-200"
                    onClick={() => toggleSort(col.key)}
                  >
                    {col.label} {sortIndicator(col.key)}
                  </button>
                </th>
              ))}
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800 text-zinc-300">
            {details.data.length === 0 ? (
              <tr>
                <td colSpan={11} className="px-3 py-6 text-center text-zinc-500">
                  Sem dados para o período selecionado.
                </td>
              </tr>
            ) : (
              details.data.map((row) => (
                <tr key={row.id} className="hover:bg-zinc-900/60">
                  <td className="whitespace-nowrap px-3 py-2">
                    {formatDate(row.created_at)}
                  </td>
                  <td className="px-3 py-2">{row.project}</td>
                  <td className="px-3 py-2">{row.agent}</td>
                  <td className="px-3 py-2">{row.user_id}</td>
                  <td className="px-3 py-2">{row.operation_type}</td>
                  <td className="px-3 py-2">{row.model}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {numberFmt.format(row.input_tokens)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {numberFmt.format(row.output_tokens)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {numberFmt.format(row.total_tokens)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {row.duration_ms != null
                      ? numberFmt.format(row.duration_ms)
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    {row.success ? (
                      <span className="text-emerald-400">ok</span>
                    ) : (
                      <span title={row.error ?? undefined} className="text-red-400">
                        erro
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm text-zinc-400">
        <span>
          {numberFmt.format(details.total)} registros — página {details.page} de{" "}
          {totalPages}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={page <= 1 || loading}
            onClick={() => goTo(page - 1)}
            className="rounded-md bg-zinc-800 px-3 py-1.5 text-zinc-100 hover:bg-zinc-700 disabled:opacity-40"
          >
            Anterior
          </button>
          <button
            type="button"
            disabled={page >= totalPages || loading}
            onClick={() => goTo(page + 1)}
            className="rounded-md bg-zinc-800 px-3 py-1.5 text-zinc-100 hover:bg-zinc-700 disabled:opacity-40"
          >
            Próxima
          </button>
        </div>
      </div>
    </div>
  );
}
