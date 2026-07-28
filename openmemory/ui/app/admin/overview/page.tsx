"use client";

import { useAdminApi } from "@/hooks/useAdminApi";
import { useAcknowledgeQueueFailuresOnMount } from "@/hooks/useAcknowledgeQueueFailuresOnMount";
import { OverviewMetrics } from "@/components/admin/OverviewMetrics";
import { PageHeader } from "@/components/shared/PageHeader";
import { useApiSessionReady } from "@/hooks/useApiSessionReady";
import { LayoutDashboard } from "lucide-react";
import { useEffect } from "react";

export default function OverviewPage() {
  const apiSessionReady = useApiSessionReady();
  const { fetchAdminOverview } = useAdminApi({ poll: apiSessionReady });
  useAcknowledgeQueueFailuresOnMount();

  useEffect(() => {
    if (!apiSessionReady) return;
    void fetchAdminOverview();
  }, [apiSessionReady, fetchAdminOverview]);

  return (
    <div>
      <PageHeader className="mb-4" icon={LayoutDashboard} title="Visão Geral" />
      <OverviewMetrics onRetry={() => void fetchAdminOverview()} />
    </div>
  );
}
