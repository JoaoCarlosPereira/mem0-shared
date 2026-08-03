"use client";

import {
  KanbanEmbedCanvas,
  type KanbanEmbedInfo,
} from "@/components/docs/KanbanEmbedCanvas";

export type KanbanHomeEmbedInfo = KanbanEmbedInfo;

type Props = {
  reloadToken?: number;
};

/**
 * Home Kanban (ADR-008): SPA same-origin sob /planka, full-bleed na aba Kanban.
 */
export function KanbanHomeCanvas({ reloadToken = 0 }: Props) {
  return <KanbanEmbedCanvas reloadToken={reloadToken} />;
}

export default KanbanHomeCanvas;
