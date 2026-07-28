"use client";

import { Install } from "@/components/dashboard/Install";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { OverviewMetrics } from "@/components/admin/OverviewMetrics";
import { APP_TAGLINE } from "@/lib/branding";
import { useAdminApi } from "@/hooks/useAdminApi";
import { useAcknowledgeQueueFailuresOnMount } from "@/hooks/useAcknowledgeQueueFailuresOnMount";
import { useApiSessionReady } from "@/hooks/useApiSessionReady";
import { useEffect } from "react";
import "@/styles/animation.css";

export default function DashboardPage() {
  const apiSessionReady = useApiSessionReady();
  // Home: one-shot fetch (no polling). Admin overview keeps poll=true.
  const { fetchAdminOverview } = useAdminApi({ poll: false });
  useAcknowledgeQueueFailuresOnMount();

  useEffect(() => {
    if (!apiSessionReady) return;
    void fetchAdminOverview();
  }, [apiSessionReady, fetchAdminOverview]);

  return (
    <div className="space-y-6">
      <p className="text-ui-body-sm uppercase tracking-widest text-slate-500 animate-fade-slide-down">
        {APP_TAGLINE}
      </p>

      <div className="border-b border-slate-800/30 pb-6 animate-fade-slide-down">
        <OverviewMetrics
          className="grid grid-cols-2 gap-4 md:grid-cols-3"
          onRetry={() => void fetchAdminOverview()}
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
