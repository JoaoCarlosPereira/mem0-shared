import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type KpiAccent = "blue" | "emerald" | "cyan" | "violet" | "amber" | "rose";

const ACCENT_STYLES: Record<KpiAccent, { border: string; bar: string; icon: string }> = {
  blue: { border: "border-blue-600", bar: "bg-blue-500", icon: "text-slate-700" },
  emerald: { border: "border-emerald-600", bar: "bg-emerald-500", icon: "text-slate-700" },
  cyan: { border: "border-cyan-600", bar: "bg-cyan-500", icon: "text-slate-700" },
  violet: { border: "border-violet-600", bar: "bg-violet-500", icon: "text-slate-700" },
  amber: { border: "border-amber-600", bar: "bg-amber-500", icon: "text-slate-700" },
  rose: { border: "border-rose-600", bar: "bg-rose-500", icon: "text-slate-700" },
};

interface KpiCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  accent?: KpiAccent;
  progress?: number;
  hint?: string;
  alert?: boolean;
}

export function KpiCard({
  label,
  value,
  icon: Icon,
  accent = "blue",
  progress,
  hint,
  alert = false,
}: KpiCardProps) {
  const styles = ACCENT_STYLES[alert ? "rose" : accent];
  const pct = progress != null ? Math.min(100, Math.max(0, progress)) : null;

  return (
    <div
      className={cn(
        "glass rounded-2xl border-l-2 p-4",
        alert ? "border-rose-600 bg-rose-500/5" : styles.border,
      )}
      data-alert={alert ? "true" : "false"}
    >
      <div className="mb-1 flex items-center justify-between">
        <p className="text-ui-label font-black uppercase tracking-widest text-slate-500">{label}</p>
        {Icon ? <Icon className={cn("h-3.5 w-3.5", styles.icon)} /> : null}
      </div>
      <div className="flex items-end justify-between gap-4">
        <h3
          className={cn(
            "text-2xl font-bold tracking-tighter",
            alert ? "text-rose-400" : "text-white",
          )}
        >
          {value}
        </h3>
        {pct != null ? (
          <div className="mb-1.5 h-1 flex-1 overflow-hidden rounded-full bg-slate-800">
            <div
              className={cn("h-full transition-all duration-700", styles.bar)}
              style={{ width: `${pct}%` }}
            />
          </div>
        ) : null}
      </div>
      {hint ? <p className="mt-1 text-ui-caption text-slate-500">{hint}</p> : null}
    </div>
  );
}
