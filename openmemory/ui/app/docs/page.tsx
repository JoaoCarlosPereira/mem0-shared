"use client";

import { KanbanHomeCanvas } from "@/components/docs/KanbanHomeCanvas";

/**
 * Aba Kanban (ADR-008): home de projetos do SPA, sem listagem Spec.
 * Documentos SDD ficam só via MCP/API.
 */
export default function KanbanHomePage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden" data-testid="kanban-home-page">
      <KanbanHomeCanvas />
    </div>
  );
}
