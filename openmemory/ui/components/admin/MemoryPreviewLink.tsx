"use client";

import Link from "next/link";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface MemoryPreviewLinkProps {
  preview: string | null | undefined;
  fullText: string | null | undefined;
  project: string;
  memoryId?: string | null;
  /** Rótulo do diálogo quando não há memory_id (gravação bruta). */
  dialogTitle?: string;
}

export function MemoryPreviewLink({
  preview,
  fullText,
  project,
  memoryId,
  dialogTitle = "Conteúdo enviado",
}: MemoryPreviewLinkProps) {
  const label = preview?.trim() || "—";

  if (memoryId) {
    return (
      <Link
        href={`/admin/projects/${encodeURIComponent(project)}/${encodeURIComponent(memoryId)}`}
        className="block max-w-md text-sm text-violet-300 hover:text-violet-200 hover:underline"
        title="Abrir memória completa"
      >
        <span className="line-clamp-2">{label}</span>
      </Link>
    );
  }

  const body = (fullText || preview || "").trim();
  if (!body) {
    return <span className="text-sm text-zinc-500">—</span>;
  }

  return (
    <Dialog>
      <DialogTrigger asChild>
        <button
          type="button"
          className="block max-w-md text-left text-sm text-violet-300 hover:text-violet-200 hover:underline"
          title="Ver conteúdo completo"
        >
          <span className="line-clamp-2">{label}</span>
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[80vh] max-w-2xl overflow-y-auto border-zinc-800 bg-zinc-950">
        <DialogHeader>
          <DialogTitle className="text-zinc-100">{dialogTitle}</DialogTitle>
        </DialogHeader>
        <p className="whitespace-pre-wrap text-sm text-zinc-300">{body}</p>
        <p className="text-xs text-zinc-500">
          Projeto: {project}. O texto acima foi enviado para extração; a memória
          final pode ter sido dividida em vários registros.
        </p>
      </DialogContent>
    </Dialog>
  );
}

export default MemoryPreviewLink;
