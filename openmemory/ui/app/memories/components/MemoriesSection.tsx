import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Category, Client } from "../../../components/types";
import { MemoryTable } from "./MemoryTable";
import { MemoryPagination } from "./MemoryPagination";
import { CreateMemoryDialog } from "./CreateMemoryDialog";
import { PageSizeSelector } from "./PageSizeSelector";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useApiSessionReady, useApiSessionStatus } from "@/hooks/useApiSessionReady";
import { parseApiError } from "@/lib/api-errors";
import { useRouter, useSearchParams } from "next/navigation";
import { MemoryTableSkeleton } from "@/skeleton/MemoryTableSkeleton";

export function MemoriesSection() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { fetchMemories } = useMemoriesApi();
  const apiSessionReady = useApiSessionReady();
  const apiSessionStatus = useApiSessionStatus();
  const [memories, setMemories] = useState<any[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const currentPage = Number(searchParams.get("page")) || 1;
  const itemsPerPage = Number(searchParams.get("size")) || 10;
  const searchQuery = searchParams.get("search") || "";
  const searchKey = searchParams.toString();
  const [selectedCategory, setSelectedCategory] = useState<Category | "all">(
    "all"
  );
  const [selectedClient, setSelectedClient] = useState<Client | "all">("all");

  useEffect(() => {
    if (!apiSessionReady) return;

    let cancelled = false;

    const loadMemories = async () => {
      setIsLoading(true);
      setLoadError(null);
      try {
        const result = await fetchMemories(
          searchQuery,
          currentPage,
          itemsPerPage
        );
        if (cancelled) return;
        setMemories(result.memories);
        setTotalItems(result.total);
        setTotalPages(result.pages);
      } catch (error: unknown) {
        if (cancelled) return;
        const message =
          error &&
          typeof error === "object" &&
          "response" in error &&
          (error as { response?: { status?: number } }).response?.status === 429
            ? "Muitas requisições — aguarde alguns segundos e tente novamente."
            : parseApiError(error, "Falha ao buscar memórias");
        setLoadError(message);
        setMemories([]);
        setTotalItems(0);
        setTotalPages(1);
        console.error("Falha ao buscar memórias:", error);
      }
      if (!cancelled) {
        setIsLoading(false);
      }
    };

    void loadMemories();
    return () => {
      cancelled = true;
    };
  }, [currentPage, itemsPerPage, fetchMemories, searchKey, searchQuery, apiSessionReady]);

  const setCurrentPage = (page: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", page.toString());
    params.set("size", itemsPerPage.toString());
    router.push(`?${params.toString()}`);
  };

  const handlePageSizeChange = (size: number) => {
    const params = new URLSearchParams(searchParams.toString());
    params.set("page", "1"); // Reset a page 1 when changing page size
    params.set("size", size.toString());
    router.push(`?${params.toString()}`);
  };

  if (isLoading || apiSessionStatus === "validating") {
    return (
      <div className="w-full bg-transparent">
        <MemoryTableSkeleton />
        <div className="flex items-center justify-between mt-4">
          <div className="h-8 w-32 animate-pulse rounded bg-slate-800" />
          <div className="h-8 w-48 animate-pulse rounded bg-slate-800" />
          <div className="h-8 w-32 animate-pulse rounded bg-slate-800" />
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <p className="text-red-400 mb-4">{loadError}</p>
        <Button
          variant="outline"
          onClick={() => {
            setLoadError(null);
            setIsLoading(true);
            void fetchMemories(searchQuery, currentPage, itemsPerPage)
              .then((result) => {
                setMemories(result.memories);
                setTotalItems(result.total);
                setTotalPages(result.pages);
              })
              .catch((error: unknown) => {
                setLoadError(parseApiError(error, "Falha ao buscar memórias"));
              })
              .finally(() => setIsLoading(false));
          }}
        >
          Tentar novamente
        </Button>
      </div>
    );
  }

  return (
    <div className="w-full bg-transparent">
      <div>
        {memories.length > 0 ? (
          <>
            <MemoryTable />
            <div className="flex items-center justify-between mt-4">
              <PageSizeSelector
                pageSize={itemsPerPage}
                onPageSizeChange={handlePageSizeChange}
              />
              <div className="mr-2 text-sm text-slate-500">
                Exibindo {(currentPage - 1) * itemsPerPage + 1} a{" "}
                {Math.min(currentPage * itemsPerPage, totalItems)} de{" "}
                {totalItems} memórias
              </div>
              <MemoryPagination
                currentPage={currentPage}
                totalPages={totalPages}
                setCurrentPage={setCurrentPage}
              />
            </div>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <div className="mb-4 rounded-full border border-slate-800 bg-slate-900/60 p-3">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="h-6 w-6 text-slate-400"
              >
                <path d="M21 9v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7"></path>
                <path d="M16 2v6h6"></path>
                <path d="M12 18v-6"></path>
                <path d="M9 15h6"></path>
              </svg>
            </div>
            <h3 className="text-lg font-medium">Nenhuma memória encontrada</h3>
            <p className="mt-1 mb-4 text-slate-400">
              {searchQuery
                ? `Nenhum resultado para "${searchQuery}"`
                : selectedCategory !== "all" || selectedClient !== "all"
                  ? "Tente ajustar seus filtros"
                  : "Crie sua primeira memória para vê-la aqui"}
            </p>
            {selectedCategory !== "all" || selectedClient !== "all" ? (
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedCategory("all");
                  setSelectedClient("all");
                }}
              >
                Limpar Filtros
              </Button>
            ) : (
              <CreateMemoryDialog />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
