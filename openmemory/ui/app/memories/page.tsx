"use client";

import { Suspense, useEffect, useState } from "react";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { MemoriesGraphSection } from "@/app/memories/MemoriesGraphPage";
import { MemoryFilters } from "@/app/memories/components/MemoryFilters";
import { PageHeader } from "@/components/shared/PageHeader";
import { Layers } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import "@/styles/animation.css";
import UpdateMemory from "@/components/shared/update-memory";
import { useUI } from "@/hooks/useUI";
import { MemoryTableSkeleton } from "@/skeleton/MemoryTableSkeleton";

function MemoriesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { updateMemoryDialog, handleCloseUpdateMemoryDialog } = useUI();
  const [activeTab, setActiveTab] = useState("lista");

  useEffect(() => {
    if (!searchParams.has("page") || !searchParams.has("size")) {
      const params = new URLSearchParams(searchParams.toString());
      if (!searchParams.has("page")) params.set("page", "1");
      if (!searchParams.has("size")) params.set("size", "20");
      router.replace(`?${params.toString()}`);
    }
  }, [router, searchParams]);

  return (
    <>
      <UpdateMemory
        memoryId={updateMemoryDialog.memoryId || ""}
        memoryContent={updateMemoryDialog.memoryContent || ""}
        open={updateMemoryDialog.isOpen}
        onOpenChange={handleCloseUpdateMemoryDialog}
      />
      <div className="space-y-3">
      <PageHeader
        className="animate-fade-slide-down"
        icon={Layers}
        title="Memórias"
        description="Busque, filtre e gerencie memórias compartilhadas"
      />
      <div className="animate-fade-slide-down">
        <MemoryFilters />
      </div>
      <div className="animate-fade-slide-down">
        <Tabs
          defaultValue="lista"
          className="mb-6"
          onValueChange={setActiveTab}
        >
          <TabsList className="bg-transparent border-b border-slate-800 rounded-none w-full justify-start gap-4 p-0">
            <TabsTrigger
              value="lista"
              className={`px-0 pb-2 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none ${
                activeTab === "lista" ? "text-white" : "text-slate-400"
              }`}
            >
              Lista
            </TabsTrigger>
            <TabsTrigger
              value="grafo"
              className={`px-0 pb-2 rounded-none data-[state=active]:border-b-2 data-[state=active]:border-primary data-[state=active]:shadow-none ${
                activeTab === "grafo" ? "text-white" : "text-slate-400"
              }`}
            >
              Grafo
            </TabsTrigger>
          </TabsList>

          <TabsContent
            value="lista"
            className="mt-6 animate-fade-slide-down delay-1"
          >
            <MemoriesSection />
          </TabsContent>

          <TabsContent
            value="grafo"
            className="mt-6 animate-fade-slide-down delay-1"
          >
            <MemoriesGraphSection />
          </TabsContent>
        </Tabs>
      </div>
      </div>
    </>
  );
}

export default function MemoriesPage() {
  return (
    <Suspense fallback={<MemoryTableSkeleton />}>
      <MemoriesPageContent />
    </Suspense>
  );
}
