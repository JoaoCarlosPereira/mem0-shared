"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useSelector } from "react-redux";
import {
  LayoutDashboard,
  ListOrdered,
  Database,
  Shield,
  ScrollText,
  HardDrive,
  Users,
} from "lucide-react";
import { selectSidebarFailedCount } from "@/store/queuesSlice";
import { useQueueFailedAlerts } from "@/hooks/useQueueFailedAlerts";
import { APP_NAME } from "@/lib/branding";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Visão Geral", href: "/admin/overview", icon: LayoutDashboard },
  { label: "Filas", href: "/admin/queues", icon: ListOrdered },
  { label: "Projetos", href: "/admin/projects", icon: Database },
  { label: "Grupos", href: "/admin/groups", icon: Users },
  { label: "Governança", href: "/admin/governance", icon: Shield },
  { label: "Backup", href: "/admin/backup", icon: HardDrive },
  { label: "Log de Auditoria", href: "/admin/audit", icon: ScrollText },
];

export function AdminSidebar() {
  const pathname = usePathname();
  useQueueFailedAlerts();
  const failedCount = useSelector(selectSidebarFailedCount);

  return (
    <nav
      aria-label="Navegação do painel admin"
      className="flex w-56 shrink-0 flex-col gap-1 border-r border-zinc-800 bg-zinc-950 p-3"
    >
      <Link
        href="/admin/overview"
        className="mb-3 flex items-center gap-2 rounded-md px-2 py-2 text-zinc-200 hover:bg-zinc-900"
      >
        <Image src="/logo.svg" alt={APP_NAME} width={24} height={24} />
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">{APP_NAME}</div>
          <div className="text-xs text-zinc-500">Admin</div>
        </div>
      </Link>
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = pathname?.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={`flex items-center justify-between gap-2 rounded-md px-3 py-2 text-sm transition-colors ${
              isActive
                ? "bg-zinc-800 text-white"
                : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
            }`}
          >
            <span className="flex items-center gap-2">
              <Icon className="h-4 w-4" />
              {item.label}
            </span>
            {item.label === "Filas" && failedCount > 0 && (
              <span
                aria-label={`${failedCount} jobs com falha`}
                className="inline-flex min-w-5 items-center justify-center rounded-full bg-red-600 px-1.5 text-xs font-semibold text-white"
              >
                {failedCount}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );
}

export default AdminSidebar;
