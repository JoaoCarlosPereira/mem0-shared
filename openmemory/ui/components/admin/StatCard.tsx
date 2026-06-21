import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface StatCardProps {
  title: string;
  value: number | string;
  // Destaque visual (borda/fundo vermelho) — usado para filas com failed > 0.
  alert?: boolean;
  // Texto auxiliar opcional (ex.: status do worker).
  hint?: string;
}

export function StatCard({ title, value, alert = false, hint }: StatCardProps) {
  return (
    <Card
      className={
        alert
          ? "border-red-600/60 bg-red-950/30"
          : "border-zinc-800 bg-zinc-900"
      }
      data-alert={alert ? "true" : "false"}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-zinc-400">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div
          className={`text-2xl font-semibold ${alert ? "text-red-400" : "text-zinc-100"}`}
        >
          {value}
        </div>
        {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
      </CardContent>
    </Card>
  );
}

export default StatCard;
