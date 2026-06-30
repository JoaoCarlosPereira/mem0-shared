import { useState } from "react";
import {
  Edit,
  MoreHorizontal,
  Trash2,
  Pause,
  Archive,
  Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useToast } from "@/hooks/use-toast";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "@/store/store";
import {
  selectMemory,
  deselectMemory,
  selectAllMemories,
  clearSelection,
} from "@/store/memoriesSlice";
import { AttributionLabel } from "@/components/shared/attribution-badge";
import { HiMiniRectangleStack } from "react-icons/hi2";
import { PiSwatches } from "react-icons/pi";
import { GoPackage } from "react-icons/go";
import { CiCalendar } from "react-icons/ci";
import { useRouter } from "next/navigation";
import Categories from "@/components/shared/categories";
import { useUI } from "@/hooks/useUI";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDate } from "@/lib/helpers";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";

export function MemoryTable() {
  const { toast } = useToast();
  const router = useRouter();
  const dispatch = useDispatch();
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const selectedMemoryIds = useSelector(
    (state: RootState) => state.memories.selectedMemoryIds
  );
  const memories = useSelector((state: RootState) => state.memories.memories);

  const { deleteMemories, updateMemoryState, isLoading, deletionPolicy } = useMemoriesApi();

  const handleDeleteMemory = async (id: string) => {
    setDeleting(true);
    try {
      await deleteMemories([id]);
      toast({
        title: "Memória excluída",
        description: "A memória foi removida com sucesso.",
      });
      setDeleteTargetId(null);
    } catch (error) {
      toast({
        title: "Não foi possível excluir",
        description:
          error instanceof Error ? error.message : "Falha ao excluir memória",
        variant: "destructive",
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      dispatch(selectAllMemories());
    } else {
      dispatch(clearSelection());
    }
  };

  const handleSelectMemory = (id: string, checked: boolean) => {
    if (checked) {
      dispatch(selectMemory(id));
    } else {
      dispatch(deselectMemory(id));
    }
  };
  const { handleOpenUpdateMemoryDialog } = useUI();

  const handleEditMemory = (memory_id: string, memory_content: string) => {
    handleOpenUpdateMemoryDialog(memory_id, memory_content);
  };

  const handleUpdateMemoryState = async (id: string, newState: string) => {
    try {
      await updateMemoryState([id], newState);
    } catch (error) {
      toast({
        title: "Erro",
        description: "Falha ao atualizar o estado da memória",
        variant: "destructive",
      });
    }
  };

  const isAllSelected =
    memories.length > 0 && selectedMemoryIds.length === memories.length;
  const isPartiallySelected =
    selectedMemoryIds.length > 0 && selectedMemoryIds.length < memories.length;

  const handleMemoryClick = (id: string) => {
    router.push(`/memory/${id}`);
  };

  return (
    <div className="rounded-md border">
      <Table className="">
        <TableHeader>
          <TableRow className="bg-zinc-800 hover:bg-zinc-800">
            <TableHead className="w-[50px] pl-4">
              <Checkbox
                className="data-[state=checked]:border-primary border-zinc-500/50"
                checked={isAllSelected}
                data-state={
                  isPartiallySelected
                    ? "indeterminate"
                    : isAllSelected
                    ? "checked"
                    : "unchecked"
                }
                onCheckedChange={handleSelectAll}
              />
            </TableHead>
            <TableHead className="border-zinc-700">
              <div className="flex items-center min-w-[600px]">
                <HiMiniRectangleStack className="mr-1" />
                Memória
              </div>
            </TableHead>
            <TableHead className="border-zinc-700">
              <div className="flex items-center">
                <PiSwatches className="mr-1" size={15} />
                Categorias
              </div>
            </TableHead>
            <TableHead className="w-[140px] border-zinc-700">
              <div className="flex items-center">
                <GoPackage className="mr-1" />
                Criado por
              </div>
            </TableHead>
            <TableHead className="w-[120px] border-zinc-700">
              <div className="flex items-center justify-center">Grupo</div>
            </TableHead>
            <TableHead className="w-[140px] border-zinc-700">
              <div className="flex items-center w-full justify-center">
                <CiCalendar className="mr-1" size={16} />
                Criada em
              </div>
            </TableHead>
            <TableHead className="text-right border-zinc-700 flex justify-center">
              <div className="flex items-center justify-end">
                <MoreHorizontal className="h-4 w-4 mr-2" />
              </div>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {memories.map((memory) => (
            <TableRow
              key={memory.id}
              className={`hover:bg-zinc-900/50 ${
                memory.state === "paused" || memory.state === "archived"
                  ? "text-zinc-400"
                  : ""
              } ${isLoading ? "animate-pulse opacity-50" : ""}`}
            >
              <TableCell className="pl-4">
                <Checkbox
                  className="data-[state=checked]:border-primary border-zinc-500/50"
                  checked={selectedMemoryIds.includes(memory.id)}
                  onCheckedChange={(checked) =>
                    handleSelectMemory(memory.id, checked as boolean)
                  }
                />
              </TableCell>
              <TableCell className="">
                {memory.state === "paused" || memory.state === "archived" ? (
                  <TooltipProvider>
                    <Tooltip delayDuration={0}>
                      <TooltipTrigger asChild>
                        <div
                          onClick={() => handleMemoryClick(memory.id)}
                          className={`font-medium ${
                            memory.state === "paused" ||
                            memory.state === "archived"
                              ? "text-zinc-400"
                              : "text-white"
                          } cursor-pointer`}
                        >
                          {memory.memory}
                        </div>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>
                          Esta memória está{" "}
                          <span className="font-bold">
                            {memory.state === "paused" ? "pausada" : "arquivada"}
                          </span>{" "}
                          e <span className="font-bold">desativada</span>.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                ) : (
                  <div
                    onClick={() => handleMemoryClick(memory.id)}
                    className={`font-medium text-white cursor-pointer`}
                  >
                    {memory.memory}
                  </div>
                )}
              </TableCell>
              <TableCell className="">
                <div className="flex flex-wrap gap-1">
                  <Categories
                    categories={memory.categories}
                    isPaused={
                      memory.state === "paused" || memory.state === "archived"
                    }
                    concat={true}
                  />
                </div>
              </TableCell>
              <TableCell className="w-[140px] text-center">
                <AttributionLabel
                  appName={memory.app_name}
                  metadata={memory.metadata}
                />
              </TableCell>
              <TableCell className="w-[120px] text-center">
                <span
                  className="inline-block rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300"
                  aria-label="Grupo do autor"
                >
                  {memory.group ?? "—"}
                </span>
              </TableCell>
              <TableCell className="w-[140px] text-center">
                {formatDate(memory.created_at)}
              </TableCell>
              <TableCell className="text-right flex justify-center">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent
                    align="end"
                    className="bg-zinc-900 border-zinc-800"
                  >
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={() => {
                        const newState =
                          memory.state === "active" ? "paused" : "active";
                        handleUpdateMemoryState(memory.id, newState);
                      }}
                    >
                      {memory?.state === "active" ? (
                        <>
                          <Pause className="mr-2 h-4 w-4" />
                          Pausar
                        </>
                      ) : (
                        <>
                          <Play className="mr-2 h-4 w-4" />
                          Retomar
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={() => {
                        const newState =
                          memory.state === "active" ? "archived" : "active";
                        handleUpdateMemoryState(memory.id, newState);
                      }}
                    >
                      <Archive className="mr-2 h-4 w-4" />
                      {memory?.state !== "archived" ? (
                        <>Arquivar</>
                      ) : (
                        <>Desarquivar</>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      className="cursor-pointer"
                      onClick={() => handleEditMemory(memory.id, memory.memory)}
                    >
                      <Edit className="mr-2 h-4 w-4" />
                      Editar
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="cursor-pointer text-red-500 focus:text-red-500"
                      disabled={deletionPolicy?.memory_delete_allowed === false}
                      onClick={() => setDeleteTargetId(memory.id)}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Excluir
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <ConfirmDeleteDialog
        open={deleteTargetId !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTargetId(null);
        }}
        title="Excluir memória?"
        description="Esta ação remove a memória permanentemente. Não pode ser desfeita."
        loading={deleting}
        onConfirm={() => {
          if (deleteTargetId) void handleDeleteMemory(deleteTargetId);
        }}
      />
    </div>
  );
}
