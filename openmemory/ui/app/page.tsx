"use client";

import { Install } from "@/components/dashboard/Install";
import Stats from "@/components/dashboard/Stats";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { PageHeader } from "@/components/shared/PageHeader";
import { APP_TAGLINE, APP_NAME } from "@/lib/branding";
import { LayoutDashboard } from "lucide-react";
import "@/styles/animation.css";

export default function DashboardPage() {
  return (
    <div className="text-white py-6">
      <div className="container">
        <div className="w-full mx-auto space-y-6">
          <PageHeader
            className="animate-fade-slide-down"
            icon={LayoutDashboard}
            title="Painel"
            description={`${APP_NAME} — ${APP_TAGLINE}`}
          />
          <div className="grid grid-cols-3 gap-6">
            {/* Memory Category Breakdown */}
            <div className="col-span-2 animate-fade-slide-down">
              <Install />
            </div>

            {/* Memories Stats */}
            <div className="col-span-1 animate-fade-slide-down delay-1">
              <Stats />
            </div>
          </div>

          <div>
            <div className="animate-fade-slide-down delay-2">
              <MemoryFilters />
            </div>
            <div className="animate-fade-slide-down delay-3">
              <MemoriesSection />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
