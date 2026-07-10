import { Badge } from "@/components/ui/badge";
import type { UsageLevel } from "@/types/admin";

const STYLES: Record<UsageLevel, string> = {
  online: "border-green-700 bg-green-950/50 text-green-300",
  offline: "border-zinc-700 bg-zinc-900 text-zinc-400",
};

function formatLabel(level: UsageLevel, offlineDays?: number | null): string {
  if (level === "online") {
    return "Online";
  }
  if (offlineDays == null) {
    return "Offline — sem interação";
  }
  if (offlineDays === 1) {
    return "Offline há 1 dia";
  }
  return `Offline há ${offlineDays} dias`;
}

interface UsageBadgeProps {
  level: UsageLevel;
  offlineDays?: number | null;
}

export function UsageBadge({ level, offlineDays }: UsageBadgeProps) {
  return (
    <Badge variant="outline" className={STYLES[level]}>
      {formatLabel(level, offlineDays)}
    </Badge>
  );
}

export default UsageBadge;
