"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const ITEMS = [
  { label: "Visão geral", href: "/admin/users" },
  { label: "Top contribuidores", href: "/admin/users/contributors" },
] as const;

export function UsersSubNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Seções de usuários"
      className="mb-6 inline-flex rounded-xl border border-zinc-800 bg-zinc-900/50 p-1"
    >
      {ITEMS.map((item) => {
        const isActive =
          item.href === "/admin/users"
            ? pathname === "/admin/users"
            : pathname?.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-zinc-800 text-white"
                : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

export default UsersSubNav;
