"use client";
import { useEffect } from "react";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useAppsApi } from "@/hooks/useAppsApi";
import { AppCard } from "./AppCard";
import { AppCardSkeleton } from "@/skeleton/AppCardSkeleton";
import { ProjectsSummary } from "./ProjectsSummary";

export function AppGrid() {
  const { fetchApps, isLoading } = useAppsApi();
  const apps = useSelector((state: RootState) => state.apps.apps);
  const filters = useSelector((state: RootState) => state.apps.filters);

  useEffect(() => {
    fetchApps({
      name: filters.searchQuery,
      is_active: filters.isActive === "all" ? undefined : filters.isActive,
      sort_by: filters.sortBy,
      sort_direction: filters.sortDirection,
      page_size: 100,
    });
  }, [fetchApps, filters]);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <AppCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  if (apps.length === 0) {
    return (
      <div className="text-center text-zinc-500 py-8">
        Nenhum projeto encontrado para os filtros aplicados
      </div>
    );
  }

  return (
    <>
      <ProjectsSummary />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {apps.map((app) => (
          <AppCard key={app.id} app={app} />
        ))}
      </div>
    </>
  );
}
