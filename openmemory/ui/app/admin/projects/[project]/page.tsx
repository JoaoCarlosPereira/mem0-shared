"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { Memory } from "@/components/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
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
import { MemoryStateActions } from "@/components/admin/MemoryStateActions";

const ALL = "all";

export default function ProjectMemoriesPage() {
  const params = useParams<{ project: string }>();
  const projectName = decodeURIComponent(params.project);
  const {
    fetchMemories,
    createMemory,
    deleteMemories,
    updateMemoryState,
  } = useMemoriesApi();

  const [items, setItems] = useState<Memory[]>([]);
  const [pages, setPages] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [stateFilter, setStateFilter] = useState<string>(ALL);
  const [selected, setSelected] = useState<string[]>([]);

  // Criação
  const [createOpen, setCreateOpen] = useState(false);
  const [newText, setNewText] = useState("");
  const [newUserId, setNewUserId] = useState("");

  // Confirmação de delete (individual ou em lote)
  const [pendingDelete, setPendingDelete] = useState<string[] | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetchMemories(search, page, 10, {
        showArchived: stateFilter === "archived" ? true : undefined,
      });
      let mems = res.memories;
      if (stateFilter !== ALL) {
        mems = mems.filter((m) => m.state === stateFilter);
      }
      setItems(mems);
      setPages(res.pages);
    } catch {
      // erros já são tratados/logados pelo hook
    }
  }, [fetchMemories, search, page, stateFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleSelect = (id: string, checked: boolean) => {
    setSelected((prev) =>
      checked ? [...prev, id] : prev.filter((x) => x !== id),
    );
  };

  const handleCreate = async () => {
    try {
      await createMemory(newText);
      toast.success("Memória enfileirada para criação");
      setCreateOpen(false);
      setNewText("");
      setNewUserId("");
      await load();
    } catch {
      toast.error("Falha ao criar memória");
    }
  };

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    try {
      await deleteMemories(pendingDelete);
      toast.success("Memória(s) deletada(s)");
      setItems((prev) => prev.filter((m) => !pendingDelete.includes(m.id)));
      setSelected([]);
    } catch {
      toast.error("Falha ao deletar");
    } finally {
      setPendingDelete(null);
    }
  };

  const changeState = async (id: string, state: string) => {
    await updateMemoryState([id], state);
    await load();
  };

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100">
          Memórias — {projectName}
        </h1>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogTrigger asChild>
            <Button size="sm">Nova Memória</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Nova Memória em {projectName}</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <Textarea
                aria-label="Conteúdo da memória"
                placeholder="Conteúdo da memória"
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
              />
              <Input
                aria-label="user_id (opcional)"
                placeholder="user_id (opcional)"
                value={newUserId}
                onChange={(e) => setNewUserId(e.target.value)}
              />
            </div>
            <DialogFooter>
              <Button
                onClick={handleCreate}
                disabled={!newText.trim()}
              >
                Criar
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <div className="mb-3 flex gap-2">
        <Input
          placeholder="Buscar memórias…"
          className="w-72"
          value={search}
          onChange={(e) => {
            setPage(1);
            setSearch(e.target.value);
          }}
        />
        <Select
          value={stateFilter}
          onValueChange={(v) => {
            setPage(1);
            setStateFilter(v);
          }}
        >
          <SelectTrigger className="w-44" aria-label="Filtrar por estado">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Todos estados</SelectItem>
            <SelectItem value="active">active</SelectItem>
            <SelectItem value="paused">paused</SelectItem>
            <SelectItem value="archived">archived</SelectItem>
          </SelectContent>
        </Select>
        {selected.length > 0 && (
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setPendingDelete(selected)}
          >
            Deletar selecionados ({selected.length})
          </Button>
        )}
      </div>

      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10" />
              <TableHead>Conteúdo</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>App</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-zinc-500">
                  Nenhuma memória encontrada
                </TableCell>
              </TableRow>
            ) : (
              items.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>
                    <Checkbox
                      aria-label={`Selecionar ${m.id}`}
                      checked={selected.includes(m.id)}
                      onCheckedChange={(c) => toggleSelect(m.id, c === true)}
                    />
                  </TableCell>
                  <TableCell className="max-w-md">
                    <Link
                      href={`/admin/projects/${encodeURIComponent(projectName)}/${m.id}`}
                      className="block truncate hover:underline"
                      title={m.memory}
                    >
                      {m.memory}
                    </Link>
                  </TableCell>
                  <TableCell>{m.state}</TableCell>
                  <TableCell>{m.app_name}</TableCell>
                  <TableCell>
                    <div className="flex justify-end">
                      <MemoryStateActions
                        state={m.state}
                        onPause={() => changeState(m.id, "paused")}
                        onArchive={() => changeState(m.id, "archived")}
                        onReactivate={() => changeState(m.id, "active")}
                        onDelete={() => setPendingDelete([m.id])}
                      />
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {pages > 1 && (
        <div className="mt-3 flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Anterior
          </Button>
          <span className="text-sm text-zinc-400">
            Página {page} de {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Próxima página
          </Button>
        </div>
      )}

      <AlertDialog
        open={pendingDelete !== null}
        onOpenChange={(o) => !o && setPendingDelete(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              {pendingDelete?.length === 1
                ? "Deletar esta memória? Esta ação não pode ser desfeita."
                : `Deletar ${pendingDelete?.length ?? 0} memórias selecionadas? Esta ação não pode ser desfeita.`}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>
              Sim, deletar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
