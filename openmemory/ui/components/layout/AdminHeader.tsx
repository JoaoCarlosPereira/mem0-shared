"use client";

import Link from "next/link";
import { Menu, ArrowLeft } from "lucide-react";
import { UserMenu } from "@/components/UserMenu";
import { Button } from "@/components/ui/button";

interface AdminHeaderProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function AdminHeader({ sidebarOpen, onToggleSidebar }: AdminHeaderProps) {
  return (
    <header className="glass sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-4 shadow-md md:px-6">
      <div className="flex items-center gap-3 md:gap-4">
        <button
          type="button"
          onClick={onToggleSidebar}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-800 transition-all hover:bg-slate-700 active:scale-90"
          aria-label={sidebarOpen ? "Fechar menu" : "Abrir menu"}
          aria-expanded={sidebarOpen}
        >
          <Menu className="h-4 w-4 text-slate-300" />
        </button>
        <div>
          <h1 className="text-base font-bold tracking-tight text-white">
            Admin <span className="font-light text-violet-400">Operações</span>
          </h1>
          <p className="hidden text-ui-caption font-black uppercase tracking-widest text-slate-500 md:block">
            Filas, governança e métricas
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        <Button
          asChild
          variant="outline"
          size="sm"
          className="border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white"
        >
          <Link href="/">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
            <span className="hidden sm:inline">Voltar ao painel</span>
          </Link>
        </Button>
        <UserMenu />
      </div>
    </header>
  );
}
