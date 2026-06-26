"use client";

import { AppFilters } from "./components/AppFilters";
import { AppGrid } from "./components/AppGrid";
import { PageHeader } from "@/components/shared/PageHeader";
import { Grid2x2 } from "lucide-react";
import "@/styles/animation.css";

export default function AppsPage() {
  return (
    <main className="flex-1 py-6">
      <div className="container">
        <PageHeader
          className="mb-4 animate-fade-slide-down"
          icon={Grid2x2}
          title="Projetos"
          description="Repositórios de memória compartilhada por projeto"
        />
        <div className="mt-1 pb-4 animate-fade-slide-down">
          <AppFilters />
        </div>
        <div className="animate-fade-slide-down delay-1">
          <AppGrid />
        </div>
      </div>
    </main>
  );
}
