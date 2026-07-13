"use client";

import { cn } from "@/lib/utils";

interface ShellTabItem {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

interface ShellTabBarProps {
  items: ShellTabItem[];
  value: string;
  onValueChange: (value: string) => void;
  className?: string;
}

export function ShellTabBar({ items, value, onValueChange, className }: ShellTabBarProps) {
  return (
    <nav
      aria-label="Abas de instalação"
      className={cn(
        "hide-scrollbar flex h-12 shrink-0 items-center gap-1 overflow-x-auto border-b border-slate-800 bg-slate-950/40 px-1",
        className,
      )}
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onValueChange(item.value)}
            className={cn(
              "flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg px-4 text-ui-body-sm font-bold transition-all",
              active
                ? "border-b-2 border-blue-500 bg-blue-500/10 text-white"
                : "border-b-2 border-transparent text-slate-500 hover:bg-slate-800/60 hover:text-slate-200",
            )}
          >
            {item.icon}
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
