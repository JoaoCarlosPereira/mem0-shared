"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useSelector } from "react-redux";
import { ChevronLeft } from "lucide-react";
import {
  BarChart3,
  LayoutDashboard,
  ListOrdered,
  Database,
  Shield,
  ScrollText,
  HardDrive,
  Users,
  UserCircle2,
} from "lucide-react";
import { selectSidebarFailedCount } from "@/store/queuesSlice";
import { useQueueFailedAlerts } from "@/hooks/useQueueFailedAlerts";
import { APP_NAME } from "@/lib/branding";
import { cn } from "@/lib/utils";

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
  { label: "Usuários", href: "/admin/users", icon: UserCircle2 },
  { label: "Governança", href: "/admin/governance", icon: Shield },
  { label: "Métricas", href: "/admin/metrics", icon: BarChart3 },
  { label: "Backup", href: "/admin/backup", icon: HardDrive },
  { label: "Log de Auditoria", href: "/admin/audit", icon: ScrollText },
];

interface AdminSidebarProps {
  open?: boolean;
  isMobile?: boolean;
  onClose?: () => void;
  onNavigate?: () => void;
}

export function AdminSidebar({
  open = true,
  isMobile = false,
  onClose,
  onNavigate,
}: AdminSidebarProps) {
  const pathname = usePathname();
  useQueueFailedAlerts();
  const failedCount = useSelector(selectSidebarFailedCount);

  return (
    <>
      {open && isMobile ? (
        <button
          type="button"
          aria-label="Fechar menu"
          className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm"
          onClick={onClose}
        />
      ) : null}

      <aside
        id="sidebar"
        aria-label="Navegação do painel admin"
        aria-hidden={!open && isMobile ? true : undefined}
        className={cn(
          "fixed top-0 left-0 z-50 flex h-full w-80 flex-col overflow-y-auto custom-scroll glass border-r border-slate-800 shadow-2xl",
          !open && "collapsed",
          open && "open",
        )}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950/20 p-6">
          <Link
            href="/admin/overview"
            className="flex min-w-0 items-center gap-3"
            onClick={onNavigate}
          >
            <Image src="/logo.svg" alt={APP_NAME} width={24} height={24} />
            <div className="min-w-0">
              <div className="truncate text-sm font-bold text-white">{APP_NAME}</div>
              <div className="text-ui-caption font-black uppercase tracking-widest text-violet-400">
                Admin
              </div>
            </div>
          </Link>
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              className="hidden h-10 w-10 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-800 hover:text-white lg:inline-flex"
              aria-label="Recolher menu"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          ) : null}
        </div>

        <nav className="flex-1 space-y-2 p-4" aria-label="Seções administrativas">
          <p className="px-2 pb-2 text-ui-body-sm font-black uppercase tracking-widest text-slate-500">
            Operações
          </p>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname?.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                onClick={onNavigate}
                className={cn(
                  "flex min-h-11 items-center justify-between gap-2 rounded-xl border border-transparent border-l-[3px] px-3 py-2.5 text-sm transition-all",
                  isActive
                    ? "nav-item-active border-l-blue-500"
                    : "border-l-transparent text-slate-400 hover:border-slate-700/50 hover:bg-slate-800/60 hover:text-slate-200",
                )}
              >
                <span className="flex items-center gap-2">
                  <Icon className="h-4 w-4 shrink-0" />
                  {item.label}
                </span>
                {item.label === "Filas" && failedCount > 0 && (
                  <span
                    aria-label={`${failedCount} jobs com falha`}
                    className="inline-flex min-w-5 items-center justify-center rounded-full bg-rose-600 px-1.5 text-xs font-semibold text-white"
                  >
                    {failedCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </aside>
    </>
  );
}

export default AdminSidebar;
