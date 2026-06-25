"use client";

import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { formatDateTimeFull } from "@/lib/datetime";
import { useAdminApi } from "@/hooks/useAdminApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { Loader2, ScrollText } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import {
  ProjectSize,
  WriteAuditFilter,
  WriteAuditLog,
} from "@/types/admin";
import { getApiUrl } from "@/lib/api-url";

const ALL = "all";
const PAGE_SIZE = 100;

export default function AuditPage() {
  // Filtros locais (não-Redux): específicos desta página.
  const { fetchWriteAudit, fetchProjectSizes } = useAdminApi({ poll: false });
  const [filters, setFilters] = useState<WriteAuditFilter>({ page: 1 });
  const [items, setItems] = useState<WriteAuditLog[]>([]);
  const [pages, setPages] = useState(0);
  const [projects, setProjects] = useState<ProjectSize[]>([]);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    fetchProjectSizes()
      .then((res) => setProjects(res.projects))
      .catch(() => {});
  }, [fetchProjectSizes]);

  const load = useCallback(async () => {
    try {
      const res = await fetchWriteAudit(filters);
      setItems(res.items);
      setPages(res.pages);
    } catch {
      // erros de listagem são silenciosos no MVP
    }
  }, [fetchWriteAudit, filters]);

  useEffect(() => {
    load();
  }, [load]);

  const updateFilter = (patch: Partial<WriteAuditFilter>) =>
    setFilters((prev) => ({ ...prev, ...patch, page: 1 }));

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const response = await axios.get(`${getApiUrl()}/admin/write-audit`, {
        headers: { Accept: "text/csv" },
        params: {
          project: filters.project || undefined,
          hostname: filters.hostname || undefined,
          from_date: filters.from_date || undefined,
          to_date: filters.to_date || undefined,
        },
        responseType: "blob",
      });
      const blobUrl = URL.createObjectURL(response.data);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = "audit-export.csv";
      a.click();
      URL.revokeObjectURL(blobUrl);
    } catch (err: any) {
      if (err?.response?.status === 400) {
        setExportError(
          "Refine os filtros — mais de 10.000 registros selecionados",
        );
      } else {
        setExportError("Falha ao exportar CSV");
      }
    } finally {
      setExporting(false);
    }
  };

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={ScrollText}
        title="Log de Auditoria"
        description="Histórico de escritas e acessos à memória compartilhada"
      />

      <div className="mb-3 flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-xs text-zinc-500">Projeto</label>
          <Select
            value={filters.project ?? ALL}
            onValueChange={(v) =>
              updateFilter({ project: v === ALL ? undefined : v })
            }
          >
            <SelectTrigger className="w-48" aria-label="Filtrar por projeto">
              <SelectValue placeholder="Todos" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>Todos os projetos</SelectItem>
              {projects.map((p) => (
                <SelectItem key={p.name} value={p.name}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="block text-xs text-zinc-500">Hostname</label>
          <Input
            className="w-44"
            placeholder="hostname"
            aria-label="Filtrar por hostname"
            onBlur={(e) => updateFilter({ hostname: e.target.value || undefined })}
          />
        </div>
        <div>
          <label className="block text-xs text-zinc-500">De</label>
          <Input
            type="date"
            className="w-40"
            aria-label="Data de início"
            onChange={(e) =>
              updateFilter({ from_date: e.target.value || undefined })
            }
          />
        </div>
        <div>
          <label className="block text-xs text-zinc-500">Até</label>
          <Input
            type="date"
            className="w-40"
            aria-label="Data de fim"
            onChange={(e) =>
              updateFilter({ to_date: e.target.value || undefined })
            }
          />
        </div>
        <Button
          variant="outline"
          size="sm"
          disabled={exporting || items.length === 0}
          onClick={handleExport}
        >
          {exporting && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
          Exportar CSV
        </Button>
      </div>

      {exportError && (
        <p className="mb-3 text-sm text-red-400" role="alert">
          {exportError}
        </p>
      )}

      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Cliente</TableHead>
              <TableHead>Projeto</TableHead>
              <TableHead>Ação</TableHead>
              <TableHead>Data/Hora</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-zinc-500">
                  Nenhum registro encontrado
                </TableCell>
              </TableRow>
            ) : (
              items.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>{row.client_name ?? row.hostname}</TableCell>
                  <TableCell>{row.project}</TableCell>
                  <TableCell>{row.action}</TableCell>
                  <TableCell>{formatDateTimeFull(row.created_at)}</TableCell>
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
            disabled={filters.page <= 1}
            onClick={() =>
              setFilters((p) => ({ ...p, page: p.page - 1 }))
            }
          >
            Anterior
          </Button>
          <span className="text-sm text-zinc-400">
            Página {filters.page} de {pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={filters.page >= pages}
            onClick={() =>
              setFilters((p) => ({ ...p, page: p.page + 1 }))
            }
          >
            Próxima página
          </Button>
        </div>
      )}
    </div>
  );
}
