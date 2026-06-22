"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { useAdminApi } from "@/hooks/useAdminApi";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ProjectSize } from "@/types/admin";
import { PageHeader } from "@/components/shared/PageHeader";
import { Database } from "lucide-react";

export default function ProjectsPage() {
  const { fetchProjectSizes } = useAdminApi({ poll: false });
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSize[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetchProjectSizes()
      .then((res) => {
        if (active) setProjects(res.projects);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [fetchProjectSizes]);

  const filtered = projects.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={Database}
        title="Projetos"
        description="Catálogo de projetos e volume de memórias"
      />
      <Input
        placeholder="Buscar projeto…"
        className="mb-3 w-72"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nome</TableHead>
              <TableHead>Memórias</TableHead>
              <TableHead>Tier</TableHead>
              <TableHead>Última atividade</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-zinc-500">
                  Carregando…
                </TableCell>
              </TableRow>
            ) : filtered.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="py-8 text-center text-zinc-500">
                  Nenhum projeto encontrado
                </TableCell>
              </TableRow>
            ) : (
              filtered.map((p) => (
                <TableRow
                  key={p.name}
                  className="cursor-pointer hover:bg-zinc-900"
                  onClick={() =>
                    router.push(`/admin/projects/${encodeURIComponent(p.name)}`)
                  }
                >
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell>{p.memory_count}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        p.partition_tier === "dedicated"
                          ? "default"
                          : "secondary"
                      }
                    >
                      {p.partition_tier}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {p.last_activity_at
                      ? format(new Date(p.last_activity_at), "dd/MM/yyyy HH:mm")
                      : "—"}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
