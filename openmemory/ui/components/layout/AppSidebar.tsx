"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  ADMIN_NAV_ITEM,
  isNavItemActive,
  MAIN_NAV_ITEMS,
} from "@/lib/shell-nav";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";

interface AppSidebarProps {
  open: boolean;
  isMobile: boolean;
  onClose: () => void;
  onNavigate: () => void;
}

export function AppSidebar({ open, isMobile, onClose, onNavigate }: AppSidebarProps) {
  const pathname = usePathname();

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
        aria-label="Navegação principal"
        aria-hidden={!open && isMobile ? true : undefined}
        className={cn(
          "fixed top-0 left-0 z-50 flex h-full w-80 flex-col overflow-y-auto custom-scroll glass border-r border-slate-800 shadow-2xl",
          !open && "collapsed",
          open && "open",
        )}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-slate-800 bg-slate-950/20 p-6">
          <Link href="/" className="flex min-w-0 items-center gap-3" onClick={onNavigate}>
            <Image src="/logo.svg" alt={APP_NAME} width={28} height={28} />
            <div className="min-w-0">
              <div className="truncate text-base font-bold text-white">{APP_NAME}</div>
              <div className="truncate text-ui-caption font-black uppercase tracking-widest text-slate-500">
                {APP_TAGLINE}
              </div>
            </div>
          </Link>
          <button
            type="button"
            onClick={onClose}
            className="hidden h-10 w-10 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-800 hover:text-white lg:inline-flex"
            aria-label="Recolher menu"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 space-y-8 p-6">
          <section>
            <div className="mb-4 flex items-center justify-between">
              <p className="text-ui-body-sm font-black uppercase tracking-widest text-slate-500">
                Navegação
              </p>
            </div>
            <nav className="space-y-2" aria-label="Seções principais">
              {MAIN_NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = isNavItemActive(pathname, item);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    onClick={onNavigate}
                    className={cn(
                      "group flex min-h-11 items-center gap-3 rounded-xl border border-slate-700/50 border-l-[3px] p-3 transition-all hover:border-blue-500/50 hover:bg-slate-700/60",
                      active
                        ? "nav-item-active border-l-blue-500"
                        : "border-l-transparent",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        active ? "text-blue-400" : "text-slate-500 group-hover:text-blue-400",
                      )}
                    />
                    <span className="text-ui-body font-bold text-slate-100">{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          </section>

          <section className="border-t border-slate-800/50 pt-6">
            <p className="mb-3 text-ui-body-sm font-black uppercase tracking-widest text-slate-500">
              Operações
            </p>
            {(() => {
              const item = ADMIN_NAV_ITEM;
              const Icon = item.icon;
              const active = isNavItemActive(pathname, item);
              return (
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={onNavigate}
                  className={cn(
                    "group flex min-h-11 items-center gap-3 rounded-xl border border-slate-700/50 border-l-[3px] p-3 transition-all hover:border-violet-500/50 hover:bg-slate-700/60",
                    active
                      ? "nav-item-active border-l-violet-500 border-violet-500/40"
                      : "border-l-transparent",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      active ? "text-violet-400" : "text-slate-500 group-hover:text-violet-400",
                    )}
                  />
                  <span className="text-ui-body font-bold text-slate-100">{item.label}</span>
                </Link>
              );
            })()}
          </section>
        </div>
      </aside>
    </>
  );
}
