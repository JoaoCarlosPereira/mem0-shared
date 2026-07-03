"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TokenSummaryRow } from "@/types/metrics";

interface TokenSummaryChartProps {
  data: TokenSummaryRow[];
}

// Paleta categórica validada para o fundo zinc-950 (scripts/validate_palette.js
// da skill dataviz: lightness band, chroma, CVD e contraste — todos PASS).
const SERIES_COLORS = ["#8b5cf6", "#0284c7", "#d97706", "#059669", "#f43f5e"];
const MAX_SERIES = SERIES_COLORS.length;
const OTHERS_KEY = "Outros";
const OTHERS_COLOR = "#71717a"; // zinc-500 — agregado, não é uma identidade

interface Totals {
  input: number;
  output: number;
  total: number;
  operations: number;
}

function computeTotals(data: TokenSummaryRow[]): Totals {
  return data.reduce(
    (acc, row) => ({
      input: acc.input + row.input_tokens,
      output: acc.output + row.output_tokens,
      total: acc.total + row.total_tokens,
      operations: acc.operations + row.operation_count,
    }),
    { input: 0, output: 0, total: 0, operations: 0 },
  );
}

/** Pivota linhas (period, group) em séries por period; top N grupos + "Outros". */
function pivot(data: TokenSummaryRow[]) {
  const totalsByGroup = new Map<string, number>();
  for (const row of data) {
    totalsByGroup.set(
      row.group,
      (totalsByGroup.get(row.group) ?? 0) + row.total_tokens,
    );
  }
  // Ordem fixa por volume total: a identidade de cor segue o grupo.
  const groups = [...totalsByGroup.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([group]) => group);
  const top = groups.slice(0, MAX_SERIES);
  const hasOthers = groups.length > MAX_SERIES;

  const byPeriod = new Map<string, Record<string, number | string>>();
  for (const row of data) {
    const bucket = byPeriod.get(row.period) ?? { period: row.period };
    const key = top.includes(row.group) ? row.group : OTHERS_KEY;
    bucket[key] = ((bucket[key] as number) ?? 0) + row.total_tokens;
    byPeriod.set(row.period, bucket);
  }
  const rows = [...byPeriod.values()].sort((a, b) =>
    String(a.period).localeCompare(String(b.period)),
  );
  const series = hasOthers ? [...top, OTHERS_KEY] : top;
  return { rows, series };
}

const numberFmt = new Intl.NumberFormat("pt-BR");

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3">
      <div className="text-xs text-zinc-400">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-zinc-100">
        {value}
      </div>
    </div>
  );
}

/**
 * Tendência de consumo de tokens por período (task_05): tiles com totais do
 * intervalo + linha por grupo da granularidade selecionada.
 */
export function TokenSummaryChart({ data }: TokenSummaryChartProps) {
  const totals = useMemo(() => computeTotals(data), [data]);
  const { rows, series } = useMemo(() => pivot(data), [data]);

  if (data.length === 0) {
    return (
      <p className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-6 text-sm text-zinc-400">
        Sem dados para o período selecionado.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="Total de tokens" value={numberFmt.format(totals.total)} />
        <StatTile label="Tokens de entrada" value={numberFmt.format(totals.input)} />
        <StatTile label="Tokens de saída" value={numberFmt.format(totals.output)} />
        <StatTile label="Operações" value={numberFmt.format(totals.operations)} />
        <StatTile
          label="Média de tokens/op"
          value={numberFmt.format(
            totals.operations ? Math.round(totals.total / totals.operations) : 0,
          )}
        />
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-4">
        <div className="h-72 w-full" data-testid="token-summary-chart">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 4, left: 8 }}>
              <CartesianGrid stroke="#27272a" vertical={false} />
              <XAxis
                dataKey="period"
                stroke="#52525b"
                tick={{ fill: "#a1a1aa", fontSize: 12 }}
                tickLine={false}
              />
              <YAxis
                stroke="#52525b"
                tick={{ fill: "#a1a1aa", fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={70}
                tickFormatter={(v: number) => numberFmt.format(v)}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#18181b",
                  border: "1px solid #3f3f46",
                  borderRadius: 8,
                  color: "#e4e4e7",
                }}
                labelStyle={{ color: "#a1a1aa" }}
                formatter={(value: number) => numberFmt.format(value)}
              />
              {series.length > 1 ? (
                <Legend wrapperStyle={{ color: "#a1a1aa", fontSize: 12 }} />
              ) : null}
              {series.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  name={name}
                  stroke={name === OTHERS_KEY ? OTHERS_COLOR : SERIES_COLORS[i]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
