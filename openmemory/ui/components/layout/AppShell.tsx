"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { AppSidebar } from "@/components/layout/AppSidebar";
import { MainHeader } from "@/components/layout/MainHeader";
import { useShellSidebar } from "@/hooks/useShellSidebar";
import { isAdminRoute, isBareRoute, isDocsBoardPath } from "@/lib/shell-nav";
import { cn } from "@/lib/utils";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const boardMode = isDocsBoardPath(pathname);
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
        <div
          className={cn(
            "min-h-0 flex-1",
            boardMode ? "flex flex-col overflow-hidden" : "custom-scroll overflow-y-auto",
          )}
        >
          <div
            className={cn(
              "panel-in w-full",
              boardMode
                ? "flex min-h-0 flex-1 flex-col px-3 py-3 md:px-4"
                : "mx-auto max-w-[1400px] px-4 py-6 md:px-8",
            )}
          >
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
