import { Badge } from "@/components/ui/badge";
import type { UsageLevel } from "@/types/admin";

const LABELS: Record<UsageLevel, string> = {
  ativo: "Ativo",
  escrita: "Só escrita",
  leitura: "Só leitura",
  inativo: "Inativo",
  sem_atividade: "Sem atividade",
};

const STYLES: Record<UsageLevel, string> = {
  ativo: "border-green-700 bg-green-950/50 text-green-300",
  escrita: "border-blue-700 bg-blue-950/50 text-blue-300",
  leitura: "border-violet-700 bg-violet-950/50 text-violet-300",
  inativo: "border-amber-700 bg-amber-950/50 text-amber-300",
  sem_atividade: "border-zinc-700 bg-zinc-900 text-zinc-400",
};

interface UsageBadgeProps {
  level: UsageLevel;
}

export function UsageBadge({ level }: UsageBadgeProps) {
  return (
    <Badge variant="outline" className={STYLES[level]}>
      {LABELS[level]}
    </Badge>
  );
}

export default UsageBadge;
