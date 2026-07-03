"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { UserCircle2 } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import {
  ACTIVITY_METRICS_HINT,
  ActivityMetricsCell,
  READS_COLUMN_LABEL,
  WRITES_COLUMN_LABEL,
} from "@/components/admin/ActivityMetricsCell";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useUserAnalyticsApi } from "@/hooks/useUserAnalyticsApi";
import type { AnalyticsOverview, GroupAnalytics } from "@/types/admin";

function errorMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function UsersDashboardPage() {
  const { fetchOverview, fetchGroupsAnalytics } = useUserAnalyticsApi();
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [groups, setGroups] = useState<GroupAnalytics[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ov, gr] = await Promise.all([fetchOverview(), fetchGroupsAnalytics()]);
      setOverview(ov);
      setGroups(gr);
    } catch (err) {
      setError(errorMessage(err, "Falha ao carregar dashboard de usuários"));
    } finally {
      setLoading(false);
    }
  }, [fetchOverview, fetchGroupsAnalytics]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <div>
      <PageHeader
        className="mb-4"
        icon={UserCircle2}
        title="Usuários"
        description="Visão centralizada de grupos, membros e uso da memória compartilhada"
      />

      {error && (
        <div
          role="alert"
          className="mb-3 rounded-md border border-red-800 bg-red-950/40 px-3 py-2 text-sm text-red-300"
        >
          {error}
        </div>
      )}

      {loading && !overview ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full rounded-lg" />
          ))}
        </div>
      ) : overview ? (
        <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard title="Total de Usuários" value={overview.total_users} />
          <StatCard title="Grupos" value={overview.total_groups} />
          <StatCard
            title="Escritas"
            value={
              <ActivityMetricsCell
                h24={overview.writes_24h}
                d7={overview.writes_7d}
                total={overview.writes_total}
              />
            }
            hint={ACTIVITY_METRICS_HINT}
          />
          <StatCard
            title="Leituras"
            value={
              <ActivityMetricsCell
                h24={overview.reads_24h}
                d7={overview.reads_7d}
                total={overview.reads_total}
              />
            }
            hint={ACTIVITY_METRICS_HINT}
          />
        </div>
      ) : null}

      <h2 className="mb-3 text-lg font-semibold text-white">Grupos de usuários</h2>
      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Grupo</TableHead>
              <TableHead>Membros</TableHead>
              <TableHead>Ativos (7d)</TableHead>
              <TableHead>{WRITES_COLUMN_LABEL}</TableHead>
              <TableHead>{READS_COLUMN_LABEL}</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-zinc-500">
                  Carregando…
                </TableCell>
              </TableRow>
            ) : groups.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="py-8 text-center text-zinc-500">
                  Nenhum grupo cadastrado
                </TableCell>
              </TableRow>
            ) : (
              groups.map((g) => (
                <TableRow key={g.id}>
                  <TableCell className="font-medium">{g.name}</TableCell>
                  <TableCell>{g.member_count}</TableCell>
                  <TableCell>{g.active_members_7d}</TableCell>
                  <TableCell>
                    <ActivityMetricsCell
                      h24={g.writes_24h}
                      d7={g.writes_7d}
                      total={g.writes_total}
                    />
                  </TableCell>
                  <TableCell>
                    <ActivityMetricsCell
                      h24={g.reads_24h}
                      d7={g.reads_7d}
                      total={g.reads_total}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <Link
                      href={`/admin/users/${g.id}`}
                      className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 hover:bg-zinc-700"
                    >
                      Ver membros
                    </Link>
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
