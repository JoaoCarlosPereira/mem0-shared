"use client";

import { Button } from "@/components/ui/button";
import { FiRefreshCcw } from "react-icons/fi";
import { Menu } from "lucide-react";
import { usePathname } from "next/navigation";
import { CreateMemoryDialog } from "@/app/memories/components/CreateMemoryDialog";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useStats } from "@/hooks/useStats";
import { useAppsApi } from "@/hooks/useAppsApi";
import { useConfig } from "@/hooks/useConfig";
import { UserMenu } from "@/components/UserMenu";
import { getPageTitle } from "@/lib/shell-nav";
import { APP_NAME_SHORT } from "@/lib/branding";

interface MainHeaderProps {
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function MainHeader({ sidebarOpen, onToggleSidebar }: MainHeaderProps) {
  const pathname = usePathname();

  const memoriesApi = useMemoriesApi();
  const appsApi = useAppsApi();
  const statsApi = useStats();
  const configApi = useConfig();

  const routeBasedFetchMapping: {
    match: RegExp;
    getFetchers: (params: Record<string, string>) => (() => Promise<unknown>)[];
  }[] = [
    {
      match: /^\/memory\/([^/]+)$/,
      getFetchers: ({ memory_id }) => [
        () => memoriesApi.fetchMemoryById(memory_id),
        () => memoriesApi.fetchAccessLogs(memory_id),
        () => memoriesApi.fetchRelatedMemories(memory_id),
      ],
    },
    {
      match: /^\/apps\/([^/]+)$/,
      getFetchers: ({ app_id }) => [
        () => appsApi.fetchAppMemories(app_id),
        () => appsApi.fetchAppAccessedMemories(app_id),
        () => appsApi.fetchAppDetails(app_id),
      ],
    },
    {
      match: /^\/memories$/,
      getFetchers: () => [memoriesApi.fetchMemories],
    },
    {
      match: /^\/apps$/,
      getFetchers: () => [appsApi.fetchApps],
    },
    {
      match: /^\/$/,
      getFetchers: () => [statsApi.fetchStats, memoriesApi.fetchMemories],
    },
    {
      match: /^\/settings$/,
      getFetchers: () => [configApi.fetchConfig],
    },
  ];

  const getFetchersForPath = (path: string) => {
    for (const route of routeBasedFetchMapping) {
      const match = path.match(route.match);
      if (match) {
        if (route.match.source.includes("memory")) {
          return route.getFetchers({ memory_id: match[1] });
        }
        if (route.match.source.includes("app")) {
          return route.getFetchers({ app_id: match[1] });
        }
        return route.getFetchers({});
      }
    }
    return [];
  };

  const handleRefresh = async () => {
    const fetchers = getFetchersForPath(pathname);
    await Promise.allSettled(fetchers.map((fn) => fn()));
  };

  const pageTitle = getPageTitle(pathname);

  return (
    <header className="glass sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-4 shadow-md md:px-6">
      <div className="flex min-w-0 items-center gap-3 md:gap-4">
        <button
          id="sidebar-toggle"
          type="button"
          onClick={onToggleSidebar}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-800 transition-all hover:bg-slate-700 active:scale-90"
          aria-label={sidebarOpen ? "Fechar menu" : "Abrir menu"}
          aria-expanded={sidebarOpen}
        >
          <Menu className="h-4 w-4 text-slate-300" />
        </button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-bold tracking-tight text-white">
            {pageTitle}{" "}
            <span className="hidden font-light text-blue-500 sm:inline">{APP_NAME_SHORT}</span>
          </h1>
          <p className="hidden text-ui-caption font-black uppercase tracking-widest text-slate-500 md:block">
            Memória compartilhada
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 md:gap-4">
        <div className="flex items-center gap-2 md:border-l md:border-slate-800 md:pl-4">
          <Button
            onClick={handleRefresh}
            variant="outline"
            size="sm"
            className="border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-white"
          >
            <FiRefreshCcw className="mr-1.5 h-3.5 w-3.5" />
            <span className="hidden sm:inline">Atualizar</span>
          </Button>
          <CreateMemoryDialog />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
