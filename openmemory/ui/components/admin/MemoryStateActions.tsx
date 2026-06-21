import { Button } from "@/components/ui/button";
import { Archive, Pause, Play, Trash2 } from "lucide-react";

type MemoryState = "active" | "paused" | "archived" | "deleted" | "quarantined";

interface MemoryStateActionsProps {
  state: MemoryState;
  onPause: () => void;
  onArchive: () => void;
  onReactivate: () => void;
  onDelete: () => void;
}

/**
 * Botões de ação inline por memória. As ações disponíveis dependem do estado:
 * - active: Pausar, Arquivar, Deletar
 * - paused/archived/quarantined: Reativar, Deletar
 */
export function MemoryStateActions({
  state,
  onPause,
  onArchive,
  onReactivate,
  onDelete,
}: MemoryStateActionsProps) {
  return (
    <div className="flex items-center gap-1">
      {state === "active" ? (
        <>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Pausar"
            title="Pausar"
            onClick={onPause}
          >
            <Pause className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-label="Arquivar"
            title="Arquivar"
            onClick={onArchive}
          >
            <Archive className="h-4 w-4" />
          </Button>
        </>
      ) : (
        <Button
          variant="ghost"
          size="sm"
          aria-label="Reativar"
          title="Reativar"
          onClick={onReactivate}
        >
          <Play className="h-4 w-4" />
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        aria-label="Deletar"
        title="Deletar"
        className="text-red-400 hover:text-red-300"
        onClick={onDelete}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
    </div>
  );
}

export default MemoryStateActions;
