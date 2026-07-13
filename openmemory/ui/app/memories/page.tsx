"use client";

import { Suspense, useEffect } from "react";
import { MemoriesSection } from "@/app/memories/components/MemoriesSection";
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

  useEffect(() => {
    if (!searchParams.has("page") || !searchParams.has("size")) {
      const params = new URLSearchParams(searchParams.toString());
      if (!searchParams.has("page")) params.set("page", "1");
      if (!searchParams.has("size")) params.set("size", "10");
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
      <div className="space-y-4">
      <PageHeader
        className="animate-fade-slide-down"
        icon={Layers}
        title="Memórias"
        description="Busque, filtre e gerencie memórias compartilhadas"
      />
      <div className="animate-fade-slide-down">
        <MemoryFilters />
      </div>
      <div className="animate-fade-slide-down delay-1">
        <MemoriesSection />
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
