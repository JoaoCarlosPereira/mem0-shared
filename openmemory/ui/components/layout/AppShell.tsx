"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { MainHeader } from "@/components/layout/MainHeader";
import { useShellSidebar } from "@/hooks/useShellSidebar";
import { isAdminRoute, isBareRoute } from "@/lib/shell-nav";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const { sidebarOpen, isMobile, toggleSidebar, closeSidebar, closeSidebarIfMobile } =
    useShellSidebar();

  if (isBareRoute(pathname)) {
    return <>{children}</>;
  }

  if (isAdminRoute(pathname)) {
    return <>{children}</>;
  }

  return (
    <div className="flex h-screen overflow-hidden text-slate-200">
      <AppSidebar
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
        <MainHeader sidebarOpen={sidebarOpen} onToggleSidebar={toggleSidebar} />
        <div className="custom-scroll min-h-0 flex-1 overflow-y-auto">
          <div className="panel-in mx-auto w-full max-w-[1400px] px-4 py-6 md:px-8">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
