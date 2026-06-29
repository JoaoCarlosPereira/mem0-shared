"use client";

import { useState } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type StrongDeleteProjectDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  projectName: string;
  memoryCount: number;
  loading?: boolean;
  onConfirm: () => void | Promise<void>;
};

/** Exige digitar o nome exato do projeto antes de confirmar exclusão irreversível. */
export function StrongDeleteProjectDialog({
  open,
  onOpenChange,
  projectName,
  memoryCount,
  loading = false,
  onConfirm,
}: StrongDeleteProjectDialogProps) {
  const [typedName, setTypedName] = useState("");

  const handleOpenChange = (next: boolean) => {
    if (!next) setTypedName("");
    onOpenChange(next);
  };

  const canConfirm = typedName === projectName && !loading;

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent className="bg-zinc-900 border-zinc-800">
        <AlertDialogHeader>
          <AlertDialogTitle>Excluir projeto permanentemente?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-zinc-400">
              <p>
                Esta ação remove o projeto{" "}
                <strong className="text-zinc-200">{projectName}</strong> e{" "}
                <strong className="text-red-400">
                  {memoryCount} memória(s)
                </strong>{" "}
                associada(s). Não pode ser desfeita.
              </p>
              <p>
                Digite o nome do projeto abaixo para confirmar:
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="py-2">
          <Label htmlFor="confirm-project-name" className="sr-only">
            Nome do projeto
          </Label>
          <Input
            id="confirm-project-name"
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            placeholder={projectName}
            className="bg-zinc-950 border-zinc-700"
            autoComplete="off"
          />
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            disabled={!canConfirm}
            onClick={(e) => {
              e.preventDefault();
              void onConfirm();
            }}
            className="bg-red-600 hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? "Excluindo…" : "Excluir projeto"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

type ConfirmDeleteDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  loading?: boolean;
  onConfirm: () => void | Promise<void>;
};

export function ConfirmDeleteDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Excluir",
  loading = false,
  onConfirm,
}: ConfirmDeleteDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-zinc-900 border-zinc-800">
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading}>Cancelar</AlertDialogCancel>
          <AlertDialogAction
            disabled={loading}
            onClick={(e) => {
              e.preventDefault();
              void onConfirm();
            }}
            className="bg-red-600 hover:bg-red-700"
          >
            {loading ? "Excluindo…" : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
