"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { format } from "date-fns";
import { useAdminApi } from "@/hooks/useAdminApi";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ArrowLeft } from "lucide-react";
import { ProjectMemory } from "@/types/admin";

function fmtDate(v: string | null): string {
  if (!v) return "—";
  try {
    // payloads do Qdrant trazem ISO; alguns backends trazem epoch em segundos.
    const d = /^\d+$/.test(v) ? new Date(Number(v) * 1000) : new Date(v);
    return format(d, "dd/MM/yyyy HH:mm:ss");
  } catch {
    return v;
  }
}

export default function ProjectMemoriesPage() {
  const params = useParams<{ project: string }>();
  const projectName = decodeURIComponent(params.project);
  const { fetchProjectMemories } = useAdminApi({ poll: false });

  const [items, setItems] = useState<ProjectMemory[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchProjectMemories(projectName, search || undefined);
      setItems(res.items);
    } catch (e: any) {
      setError(e?.message || "Falha ao carregar memórias do projeto");
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fetchProjectMemories, projectName, search]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <Link
        href="/admin/projects"
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200"
      >
        <ArrowLeft className="h-4 w-4" /> Projetos
      </Link>
      <h1 className="mb-1 text-xl font-semibold text-zinc-100">
        Memórias — {projectName}
      </h1>
      <p className="mb-4 text-sm text-zinc-500">
        Leitura direta do store compartilhado (Qdrant), indexada por projeto.
      </p>

      <div className="mb-3 flex gap-2">
        <Input
          placeholder="Buscar memórias (semântico)…"
          className="w-80"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") load();
          }}
        />
        <Button variant="outline" size="sm" onClick={load}>
          Buscar
        </Button>
      </div>

      {error && (
        <p className="mb-3 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}

      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Conteúdo</TableHead>
              <TableHead className="w-48">Criado em</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={2} className="py-8 text-center text-zinc-500">
                  Carregando…
                </TableCell>
              </TableRow>
            ) : items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={2} className="py-8 text-center text-zinc-500">
                  Nenhuma memória encontrada neste projeto
                </TableCell>
              </TableRow>
            ) : (
              items.map((m) => (
                <TableRow key={m.id}>
                  <TableCell className="text-zinc-200">{m.memory}</TableCell>
                  <TableCell className="text-zinc-400">
                    {fmtDate(m.created_at)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {!loading && items.length > 0 && (
        <p className="mt-2 text-xs text-zinc-500">{items.length} memória(s).</p>
      )}
    </div>
  );
}
