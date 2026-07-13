import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface GlassPanelProps {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
  accent?: "blue" | "violet" | "none";
}

export function GlassPanel({
  title,
  description,
  children,
  className,
  accent = "blue",
}: GlassPanelProps) {
  const accentBorder =
    accent === "violet"
      ? "border-l-violet-500"
      : accent === "blue"
        ? "border-l-blue-500"
        : "border-l-transparent";

  return (
    <section
      className={cn(
        "glass overflow-hidden rounded-2xl border border-slate-800 border-l-[3px] shadow-sm",
        accentBorder,
        className,
      )}
    >
      {title ? (
        <header className="border-b border-slate-800/60 bg-slate-900/40 px-5 py-4 md:px-6">
          <h2 className="text-lg font-bold tracking-tight text-white">{title}</h2>
          {description ? (
            <p className="mt-1 text-ui-body-sm uppercase tracking-widest text-slate-500">
              {description}
            </p>
          ) : null}
        </header>
      ) : null}
      <div className="p-5 md:p-6">{children}</div>
    </section>
  );
}
