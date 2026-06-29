"use client";
import { Archive, Pause, Play, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { FiTrash2 } from "react-icons/fi";
import { useSelector, useDispatch } from "react-redux";
import { RootState } from "@/store/store";
import { clearSelection } from "@/store/memoriesSlice";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useRouter, useSearchParams } from "next/navigation";
import { debounce } from "lodash";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import FilterComponent from "./FilterComponent";
import { clearFilters } from "@/store/filtersSlice";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";

export function MemoryFilters() {
  const dispatch = useDispatch();
  const selectedMemoryIds = useSelector(
    (state: RootState) => state.memories.selectedMemoryIds
  );
  const { deleteMemories, updateMemoryState, fetchMemories, deletionPolicy } =
    useMemoriesApi();
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeFilters = useSelector((state: RootState) => state.filters.apps);

  const inputRef = useRef<HTMLInputElement>(null);
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteSelected = async () => {
    setDeleting(true);
    try {
      await deleteMemories(selectedMemoryIds);
      dispatch(clearSelection());
      toast.success("Memória(s) excluída(s) com sucesso.");
      setBulkDeleteOpen(false);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Falha ao excluir memórias",
      );
    } finally {
      setDeleting(false);
    }
  };

  const handleArchiveSelected = async () => {
    try {
      await updateMemoryState(selectedMemoryIds, "archived");
    } catch (error) {
      console.error("Failed to archive memories:", error);
    }
  };

  const handlePauseSelected = async () => {
    try {
      await updateMemoryState(selectedMemoryIds, "paused");
    } catch (error) {
      console.error("Failed to pause memories:", error);
    }
  };

  const handleResumeSelected = async () => {
    try {
      await updateMemoryState(selectedMemoryIds, "active");
    } catch (error) {
      console.error("Failed to resume memories:", error);
    }
  };

  const handleSearch = debounce((query: string) => {
    const params = new URLSearchParams(searchParams.toString());
    const trimmed = query.trim();
    if (trimmed) {
      params.set("search", trimmed);
    } else {
      params.delete("search");
    }
    params.set("page", "1");
    if (!params.has("size")) {
      params.set("size", "10");
    }
    router.push(`/memories?${params.toString()}`);
  }, 300);

  useEffect(() => {
    // if the url has a search param, set the input value to the search param
    if (searchParams.get("search")) {
      if (inputRef.current) {
        inputRef.current.value = searchParams.get("search") || "";
        inputRef.current.focus();
      }
    }
  }, []);

  const handleClearAllFilters = async () => {
    dispatch(clearFilters());
    await fetchMemories(); // Fetch memories without any filters
  };

  const hasActiveFilters =
    activeFilters.selectedApps.length > 0 ||
    activeFilters.selectedCategories.length > 0;

  return (
    <div className="flex flex-col md:flex-row gap-4 mb-4">
      <div className="relative flex-1">
        <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <Input
          ref={inputRef}
          placeholder="Buscar memórias..."
          className="pl-8 bg-zinc-950 border-zinc-800 max-w-[500px]"
          onChange={(e) => handleSearch(e.target.value)}
        />
      </div>
      <div className="flex gap-2">
        <FilterComponent />
        {hasActiveFilters && (
          <Button
            variant="outline"
            className="bg-zinc-900 text-zinc-300 hover:bg-zinc-800"
            onClick={handleClearAllFilters}
          >
            Limpar Filtros
          </Button>
        )}
        {selectedMemoryIds.length > 0 && (
          <>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="outline"
                  className="border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800"
                >
                  Ações
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="bg-zinc-900 border-zinc-800"
              >
                <DropdownMenuItem onClick={handleArchiveSelected}>
                  <Archive className="mr-2 h-4 w-4" />
                  Arquivar Selecionadas
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handlePauseSelected}>
                  <Pause className="mr-2 h-4 w-4" />
                  Pausar Selecionadas
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleResumeSelected}>
                  <Play className="mr-2 h-4 w-4" />
                  Retomar Selecionadas
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={() => setBulkDeleteOpen(true)}
                  className="text-red-500"
                  disabled={
                    deletionPolicy?.memory_delete_allowed === false ||
                    (selectedMemoryIds.length > 1 &&
                      deletionPolicy?.bulk_delete_allowed === false)
                  }
                >
                  <FiTrash2 className="mr-2 h-4 w-4" />
                  Excluir Selecionadas
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        )}
      </div>
      <ConfirmDeleteDialog
        open={bulkDeleteOpen}
        onOpenChange={setBulkDeleteOpen}
        title={`Excluir ${selectedMemoryIds.length} memória(s)?`}
        description="Esta ação remove as memórias selecionadas permanentemente. Não pode ser desfeita."
        confirmLabel="Excluir selecionadas"
        loading={deleting}
        onConfirm={handleDeleteSelected}
      />
    </div>
  );
}
