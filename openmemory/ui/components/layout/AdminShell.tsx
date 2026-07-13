"use client";

import type { ReactNode } from "react";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import { AdminHeader } from "@/components/layout/AdminHeader";
import { useShellSidebar } from "@/hooks/useShellSidebar";
import { cn } from "@/lib/utils";

interface AdminShellProps {
  children: ReactNode;
}

export function AdminShell({ children }: AdminShellProps) {
  const { sidebarOpen, isMobile, toggleSidebar, closeSidebar, closeSidebarIfMobile } =
    useShellSidebar();

  return (
    <div className="flex h-screen overflow-hidden text-slate-200">
      <AdminSidebar
        open={sidebarOpen}
        isMobile={isMobile}
        onClose={closeSidebar}
        onNavigate={closeSidebarIfMobile}
      />
      <main
        id="main-content"
        className={cn(
          "main-content flex min-h-0 min-w-0 flex-1 flex-col",
          !sidebarOpen && "full",
        )}
      >
        <AdminHeader sidebarOpen={sidebarOpen} onToggleSidebar={toggleSidebar} />
        <div className="custom-scroll min-h-0 flex-1 overflow-y-auto">
          <div className="panel-in mx-auto w-full max-w-[1400px] px-4 py-6 md:px-8">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
