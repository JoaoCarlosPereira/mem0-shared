import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  size?: "default" | "large";
  className?: string;
}

export function PageHeader({
  title,
  description,
  icon: Icon,
  size = "default",
  className,
}: PageHeaderProps) {
  const isLarge = size === "large";

  return (
    <div className={cn("flex items-start gap-3", className)}>
      {Icon ? (
        <div
          className={cn(
            "flex shrink-0 items-center justify-center rounded-2xl border border-blue-500/20 bg-blue-600/10 shadow-inner",
            isLarge ? "h-14 w-14" : "h-12 w-12",
          )}
        >
          <Icon
            className={cn("text-blue-400", isLarge ? "h-7 w-7" : "h-5 w-5")}
          />
        </div>
      ) : null}
      <div className="min-w-0">
        <h1
          className={cn(
            "font-bold tracking-tight text-white",
            isLarge ? "text-3xl" : "text-2xl",
          )}
        >
          {title}
        </h1>
        {description ? (
          <p
            className={cn(
              "text-slate-500",
              isLarge
                ? "mt-1 text-ui-body uppercase tracking-[0.15em]"
                : "mt-1 text-ui-body-sm uppercase tracking-widest",
            )}
          >
            {description}
          </p>
        ) : null}
      </div>
    </div>
  );
}
