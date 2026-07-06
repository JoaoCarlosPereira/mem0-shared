"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Users } from "lucide-react";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { UsageBadge } from "@/components/admin/UsageBadge";
import {
  ACTIVITY_METRICS_HINT,
  ActivityMetricsCell,
  READS_COLUMN_LABEL,
  WRITES_COLUMN_LABEL,
} from "@/components/admin/ActivityMetricsCell";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useUserAnalyticsApi } from "@/hooks/useUserAnalyticsApi";
import { ActorLabel } from "@/components/shared/attribution-badge";
import type { GroupAnalyticsDetail } from "@/types/admin";

function errorMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

export default function GroupUsersPage() {
  const params = useParams<{ groupId: string }>();
  const groupId = params.groupId;
  const { fetchGroupAnalytics } = useUserAnalyticsApi();
  const [data, setData] = useState<GroupAnalyticsDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fetchGroupAnalytics(groupId));
    } catch (err) {
      setError(errorMessage(err, "Falha ao carregar membros do grupo"));
    } finally {
      setLoading(false);
    }
  }, [fetchGroupAnalytics, groupId]);

  useEffect(() => {
    void load();
  }, [load]);

  const group = data?.group;

  return (
    <div>
      <Link
        href="/admin/users"
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200"
      >
        <ArrowLeft className="h-4 w-4" /> Usuários
      </Link>

      <PageHeader
        className="mb-4"
        icon={Users}
        title={group ? `Grupo — ${group.name}` : "Grupo"}
        description="Membros e indicadores de uso da memória compartilhada"
      />

      {error && (
        <p className="mb-3 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}

      {group && (
        <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard title="Membros" value={group.member_count} />
          <StatCard title="Ativos (7d)" value={group.active_members_7d} />
          <StatCard
            title="Escritas"
            value={
              <ActivityMetricsCell
                h24={group.writes_24h}
                d7={group.writes_7d}
                total={group.writes_total}
              />
            }
            hint={ACTIVITY_METRICS_HINT}
          />
          <StatCard
            title="Leituras"
            value={
              <ActivityMetricsCell
                h24={group.reads_24h}
                d7={group.reads_7d}
                total={group.reads_total}
              />
            }
            hint={ACTIVITY_METRICS_HINT}
          />
        </div>
      )}

      <div className="rounded-md border border-zinc-800">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Usuário</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>{WRITES_COLUMN_LABEL}</TableHead>
              <TableHead>{READS_COLUMN_LABEL}</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-zinc-500">
                  Carregando…
                </TableCell>
              </TableRow>
            ) : !data?.members.length ? (
              <TableRow>
                <TableCell colSpan={5} className="py-8 text-center text-zinc-500">
                  Nenhum membro neste grupo
                </TableCell>
              </TableRow>
            ) : (
              data.members.map((m) => (
                <TableRow key={m.user_id}>
                  <TableCell>
                    <ActorLabel
                      hostname={m.user_id}
                      displayName={m.display_name}
                      avatarUrl={m.avatar_url}
                    />
                  </TableCell>
                  <TableCell>
                    <UsageBadge level={m.usage_level} />
                  </TableCell>
                  <TableCell>
                    <ActivityMetricsCell
                      h24={m.writes_24h}
                      d7={m.writes_7d}
                      total={m.writes_total}
                    />
                  </TableCell>
                  <TableCell>
                    <ActivityMetricsCell
                      h24={m.reads_24h}
                      d7={m.reads_7d}
                      total={m.reads_total}
                    />
                  </TableCell>
                  <TableCell className="text-right">
                    <Link
                      href={`/admin/users/${groupId}/${encodeURIComponent(m.user_id)}`}
                      className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-100 hover:bg-zinc-700"
                    >
                      Detalhes
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
