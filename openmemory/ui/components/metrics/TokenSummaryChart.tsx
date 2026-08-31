"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TokenSummaryRow } from "@/types/metrics";
import { Card, CardContent } from "@/components/ui/card";

interface TokenSummaryChartProps {
  data: TokenSummaryRow[];
}

const SERIES_COLORS = ["#8b5cf6", "#06b6d4", "#f59e0b", "#10b981", "#ef4444"];
const MAX_SERIES = SERIES_COLORS.length;
const OTHERS_KEY = "Outros";
const OTHERS_COLOR = "#71717a";

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

/** Fold backend default project label into the chart's "Others" bucket. */
function normalizeGroup(group: string): string {
  return group === "unknown" ? OTHERS_KEY : group;
}

/** Pivots lines (period, group) into series by period; top N groups + "Others". */
function pivot(data: TokenSummaryRow[]) {
  const totalsByGroup = new Map<string, number>();
  for (const row of data) {
    const group = normalizeGroup(row.group);
    totalsByGroup.set(group, (totalsByGroup.get(group) ?? 0) + row.total_tokens);
  }
  const ranked = [...totalsByGroup.entries()]
    .filter(([group]) => group !== OTHERS_KEY)
    .sort((a, b) => b[1] - a[1])
    .map(([group]) => group);
  const top = ranked.slice(0, MAX_SERIES);
  const hasOthers =
    ranked.length > MAX_SERIES || (totalsByGroup.get(OTHERS_KEY) ?? 0) > 0;

  const byPeriod = new Map<string, Record<string, number | string>>();
  for (const row of data) {
    const bucket = byPeriod.get(row.period) ?? { period: row.period };
    const group = normalizeGroup(row.group);
    const key = top.includes(group) ? group : OTHERS_KEY;
    bucket[key] = ((bucket[key] as number) ?? 0) + row.total_tokens;
    byPeriod.set(row.period, bucket);
  }
  const rows = [...byPeriod.values()].sort((a, b) => String(a.period).localeCompare(String(b.period)));
  const series = hasOthers ? [...top, OTHERS_KEY] : top;
  return { rows, series };
}

const numberFmt = new Intl.NumberFormat("pt-BR");

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/95 p-3 shadow-xl backdrop-blur-sm">
      <div className="mb-2 text-xs font-medium text-zinc-500">{label}</div>
      <div className="space-y-1">
        {payload.map((entry: any, index: number) => (
          <div key={index} className="flex items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
              <span className="text-zinc-400">{entry.name}</span>
            </div>
            <span className="font-mono font-medium text-zinc-100">{numberFmt.format(entry.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function TokenSummaryChart({ data }: TokenSummaryChartProps) {
  const totals = useMemo(() => computeTotals(data), [data]);
  const { rows, series } = useMemo(() => pivot(data), [data]);

  if (data.length === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex h-72 items-center justify-center text-sm text-zinc-500">
          Sem dados para o período selecionado.
        </CardContent>
      </Card>
    );
  }

  const kpis = [
    ["Total de tokens", totals.total],
    ["Entrada", totals.input],
    ["Saída", totals.output],
    ["Operações", totals.operations],
    ["Média/op", totals.operations ? Math.round(totals.total / totals.operations) : 0],
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        {kpis.map(([label, value]) => (
          <Card key={label} className="border-zinc-800/50 bg-zinc-900/40">
            <CardContent className="p-4">
              <p className="text-[10px] font-medium uppercase tracking-wider text-zinc-500">{label}</p>
              <p className="mt-1 text-lg font-bold tabular-nums text-zinc-100">{numberFmt.format(value as number)}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card className="border-zinc-800/50 bg-zinc-900/40">
        <CardContent className="p-6">
          <div className="h-[400px] w-full" data-testid="token-summary-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={rows} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
                <defs>
                  {series.map((name, i) => {
                    const color = name === OTHERS_KEY ? OTHERS_COLOR : SERIES_COLORS[i];
                    return (
                      <linearGradient key={`gradient-${i}`} id={`gradient-${i}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    );
                  })}
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#27272a" />
                <XAxis dataKey="period" axisLine={false} tickLine={false} tick={{ fill: "#71717a", fontSize: 12 }} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "#71717a", fontSize: 12 }} tickFormatter={(value: number) => numberFmt.format(value)} />
                <Tooltip content={<CustomTooltip />} />
                <Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{ paddingBottom: "20px", fontSize: "12px", color: "#a1a1aa" }} />
                {series.map((name, i) => {
                  const color = name === OTHERS_KEY ? OTHERS_COLOR : SERIES_COLORS[i];
                  return (
                    <Area key={name} type="monotone" dataKey={name} name={name} stroke={color} strokeWidth={2.5} fill={`url(#gradient-${i})`} connectNulls />
                  );
                })}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
