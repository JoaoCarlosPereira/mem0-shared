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
            "flex shrink-0 items-center justify-center rounded-lg border border-violet-500/25 bg-violet-500/10",
            isLarge ? "h-12 w-12" : "h-10 w-10",
          )}
        >
          <Icon
            className={cn("text-violet-400", isLarge ? "h-6 w-6" : "h-5 w-5")}
          />
        </div>
      ) : null}
      <div className="min-w-0">
        <h1
          className={cn(
            "font-semibold tracking-tight text-zinc-100",
            isLarge ? "text-3xl font-bold" : "text-xl",
          )}
        >
          {title}
        </h1>
        {description ? (
          <p
            className={cn(
              "text-zinc-500",
              isLarge ? "mt-1 text-base" : "mt-0.5 text-sm",
            )}
          >
            {description}
          </p>
        ) : null}
      </div>
    </div>
  );
}
