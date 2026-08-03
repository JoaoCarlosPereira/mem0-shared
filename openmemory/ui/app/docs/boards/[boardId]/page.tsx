"use client";

import { use } from "react";
import { KanbanEmbedCanvas } from "@/components/docs/KanbanEmbedCanvas";

type Props = {
  params: Promise<{ boardId: string }>;
};

/**
 * Deep-link compartilhável de um quadro Kanban.
 * Ex.: https://memorias.sysmo.com.br/docs/boards/1833672064557385241
 */
export default function KanbanBoardPage({ params }: Props) {
  const { boardId } = use(params);
  return (
    <div
      className="flex min-h-0 flex-1 flex-col overflow-hidden"
      data-testid="kanban-board-page"
    >
      <KanbanEmbedCanvas boardId={boardId} />
    </div>
  );
}
