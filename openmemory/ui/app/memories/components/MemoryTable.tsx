import { useState, type MouseEvent, type KeyboardEvent } from "react";
import {
  Edit,
  MoreHorizontal,
  Trash2,
  Pause,
  Archive,
  Play,
  ArrowUpRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
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
import { resolveCreatorAttribution } from "@/components/shared/attribution-badge";
import { CreatorAvatar } from "@/components/shared/creator-avatar";
import { useRouter } from "next/navigation";
import { useUI } from "@/hooks/useUI";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDate } from "@/lib/helpers";
import { ConfirmDeleteDialog } from "@/components/shared/ConfirmDeleteDialog";
import { groupCardTone } from "@/lib/group-card-tone";
import { cn } from "@/lib/utils";

const PREVIEW_MAX_CHARS = 110;

function memoryPreview(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= PREVIEW_MAX_CHARS) {
    return normalized;
  }
  return `${normalized.slice(0, PREVIEW_MAX_CHARS).trimEnd()}…`;
}

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

  const { deleteMemories, updateMemoryState, isLoading, deletionPolicy } =
    useMemoriesApi();

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

  const stopCardNav = (event: MouseEvent) => {
    event.stopPropagation();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2.5 px-0.5">
        <Checkbox
          className="border-slate-500 data-[state=checked]:border-primary"
          checked={isAllSelected}
          data-state={
            isPartiallySelected
              ? "indeterminate"
              : isAllSelected
                ? "checked"
                : "unchecked"
          }
          onCheckedChange={handleSelectAll}
          aria-label="Selecionar todas as memórias"
        />
        <span className="text-sm text-slate-400">
          {selectedMemoryIds.length > 0
            ? `${selectedMemoryIds.length} selecionada(s)`
            : "Selecionar todas"}
        </span>
      </div>

      <TooltipProvider delayDuration={200}>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {memories.map((memory) => {
            const attribution = resolveCreatorAttribution({
              appName: memory.app_name,
              clientName: memory.created_by_client,
              hostname: memory.created_by_hostname,
              displayName: memory.created_by_display_name,
              avatarUrl: memory.created_by_avatar_url,
              metadata: memory.metadata,
            });
            const tone = groupCardTone(
              memory.group,
              attribution.label || memory.created_by_hostname,
            );
            const isInactive =
              memory.state === "paused" || memory.state === "archived";
            const selected = selectedMemoryIds.includes(memory.id);
            const preview = memoryPreview(memory.memory);
            const groupLabel = memory.group?.trim() || null;

            const openMemory = () => handleMemoryClick(memory.id);
            const onCardKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                openMemory();
              }
            };

            return (
              <article
                key={memory.id}
                role="link"
                tabIndex={0}
                onClick={openMemory}
                onKeyDown={onCardKeyDown}
                className={cn(
                  "group/card relative flex min-h-[168px] cursor-pointer flex-col overflow-hidden rounded-2xl border bg-gradient-to-b p-0 shadow-lg transition-all duration-200 outline-none",
                  "hover:-translate-y-0.5 hover:shadow-xl focus-visible:ring-2 focus-visible:ring-blue-500/50",
                  tone.border,
                  tone.borderHover,
                  tone.wash,
                  tone.glow,
                  selected && `ring-2 ${tone.ring}`,
                  isInactive && "opacity-65",
                  isLoading && "animate-pulse opacity-50",
                )}
                data-group={memory.group ?? ""}
                aria-label={`Abrir memória${groupLabel ? ` · ${groupLabel}` : ""}: ${preview}`}
              >
                <div className={cn("h-1 w-full shrink-0", tone.accent)} />

                <div className="flex flex-1 flex-col p-4 pt-3">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <div
                      className="opacity-70 transition-opacity group-hover/card:opacity-100"
                      onClick={stopCardNav}
                      onKeyDown={(e) => e.stopPropagation()}
                    >
                      <Checkbox
                        className="border-slate-500 data-[state=checked]:border-primary"
                        checked={selected}
                        onCheckedChange={(checked) =>
                          handleSelectMemory(memory.id, checked as boolean)
                        }
                        aria-label={`Selecionar memória ${memory.id}`}
                      />
                    </div>

                    <div className="flex items-center gap-1">
                      {groupLabel ? (
                        <span
                          className={cn(
                            "max-w-[9rem] truncate rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                            tone.chip,
                          )}
                          title={groupLabel}
                        >
                          {groupLabel}
                        </span>
                      ) : null}
                      {isInactive ? (
                        <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
                          {memory.state === "paused" ? "Pausada" : "Arquivada"}
                        </span>
                      ) : null}
                      <div
                        className="opacity-0 transition-opacity group-hover/card:opacity-100 group-focus-within/card:opacity-100"
                        onClick={stopCardNav}
                      >
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 shrink-0 text-slate-400 hover:bg-slate-800/80 hover:text-slate-100"
                              aria-label="Ações da memória"
                            >
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent
                            align="end"
                            className="glass border-slate-800"
                          >
                            <DropdownMenuItem
                              className="cursor-pointer"
                              onClick={() => {
                                const newState =
                                  memory.state === "active"
                                    ? "paused"
                                    : "active";
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
                                  memory.state === "active"
                                    ? "archived"
                                    : "active";
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
                              onClick={() =>
                                handleEditMemory(memory.id, memory.memory)
                              }
                            >
                              <Edit className="mr-2 h-4 w-4" />
                              Editar
                            </DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              className="cursor-pointer text-red-500 focus:text-red-500"
                              disabled={
                                deletionPolicy?.memory_delete_allowed === false
                              }
                              onClick={() => setDeleteTargetId(memory.id)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Excluir
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  </div>

                  {isInactive ? (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <p className="mb-4 line-clamp-2 flex-1 text-[15px] font-medium leading-snug text-slate-400">
                          {preview}
                        </p>
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
                  ) : (
                    <p className="mb-4 line-clamp-2 flex-1 text-[15px] font-medium leading-snug text-slate-100">
                      {preview}
                    </p>
                  )}

                  <div className="mt-auto flex items-center justify-between gap-3 border-t border-white/5 pt-3">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span
                          className="inline-flex shrink-0 rounded-full ring-2 ring-slate-800/90 transition-transform group-hover/card:scale-105"
                          onClick={stopCardNav}
                          aria-label={`Criado por ${attribution.label}`}
                        >
                          <CreatorAvatar
                            attribution={attribution}
                            size={28}
                            className="h-7 w-7"
                          />
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p>{attribution.label}</p>
                        {groupLabel ? (
                          <p className="text-xs text-slate-400">{groupLabel}</p>
                        ) : null}
                      </TooltipContent>
                    </Tooltip>

                    <div className="flex min-w-0 items-center gap-2">
                      <time
                        className="truncate text-xs tabular-nums text-slate-400"
                        dateTime={String(memory.created_at)}
                      >
                        {formatDate(memory.created_at)}
                      </time>
                      <ArrowUpRight
                        className="h-3.5 w-3.5 shrink-0 text-slate-600 opacity-0 transition-all group-hover/card:translate-x-0.5 group-hover/card:-translate-y-0.5 group-hover/card:text-slate-300 group-hover/card:opacity-100"
                        aria-hidden
                      />
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </TooltipProvider>

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
