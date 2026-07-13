"use client";

import { useEffect } from "react";
import { useSelector } from "react-redux";
import { useApiSessionReady } from "@/hooks/useApiSessionReady";
import { Install } from "@/components/dashboard/Install";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { KpiCard } from "@/components/shared/KpiCard";
import { APP_TAGLINE } from "@/lib/branding";
import { Layers, LayoutGrid } from "lucide-react";
import { useStats } from "@/hooks/useStats";
import { RootState } from "@/store/store";
import "@/styles/animation.css";

export default function DashboardPage() {
  const apiSessionReady = useApiSessionReady();
  const { fetchStats } = useStats();
  const totalMemories = useSelector((state: RootState) => state.profile.totalMemories);
  const totalApps = useSelector((state: RootState) => state.profile.totalApps);

  useEffect(() => {
    if (!apiSessionReady) return;
    void fetchStats();
  }, [apiSessionReady, fetchStats]);

  return (
    <div className="space-y-6">
      <p className="text-ui-body-sm uppercase tracking-widest text-slate-500 animate-fade-slide-down">
        {APP_TAGLINE}
      </p>

      <div
        id="metrics-panel"
        className="grid grid-cols-1 gap-4 border-b border-slate-800/30 pb-6 sm:grid-cols-2"
      >
        <KpiCard label="Total de Memórias" value={totalMemories} icon={Layers} accent="blue" />
        <KpiCard
          label="Projetos Conectados"
          value={totalApps}
          icon={LayoutGrid}
          accent="emerald"
        />
      </div>

      <div className="animate-fade-slide-down">
        <Install />
      </div>

      <div>
        <div className="animate-fade-slide-down delay-1">
          <MemoryFilters />
        </div>
        <div className="animate-fade-slide-down delay-2">
          <MemoriesSection />
        </div>
      </div>
    </div>
  );
}
