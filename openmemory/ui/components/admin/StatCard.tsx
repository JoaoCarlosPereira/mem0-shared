import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { KpiCard } from "@/components/shared/KpiCard";

interface StatCardProps {
  title: string;
  value: number | string | ReactNode;
  alert?: boolean;
  hint?: string;
  icon?: LucideIcon;
  accent?: "blue" | "emerald" | "cyan" | "violet" | "amber" | "rose";
}

export function StatCard({
  title,
  value,
  alert = false,
  hint,
  icon,
  accent = "blue",
}: StatCardProps) {
  const displayValue: string | number =
    typeof value === "number" || typeof value === "string" ? value : "—";

  return (
    <KpiCard
      label={title}
      value={displayValue}
      hint={hint}
      alert={alert}
      icon={icon}
      accent={accent}
    />
  );
}

export default StatCard;
