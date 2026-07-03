/** Exibe métricas de atividade no formato 24h / 7d / total. */

interface ActivityMetricsCellProps {
  h24: number;
  d7: number;
  total: number;
}

export function ActivityMetricsCell({ h24, d7, total }: ActivityMetricsCellProps) {
  return (
    <span className="tabular-nums text-sm">
      <span className="text-zinc-100">{h24}</span>
      <span className="text-zinc-600"> / </span>
      <span className="text-zinc-300">{d7}</span>
      <span className="text-zinc-600"> / </span>
      <span className="text-zinc-400">{total}</span>
    </span>
  );
}

export const ACTIVITY_METRICS_HINT = "24h / 7d / total";
export const WRITES_COLUMN_LABEL = `Escritas (${ACTIVITY_METRICS_HINT})`;
export const READS_COLUMN_LABEL = `Leituras (${ACTIVITY_METRICS_HINT})`;

export default ActivityMetricsCell;
