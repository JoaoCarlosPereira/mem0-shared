"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, User } from "lucide-react";
import { formatDateTimeFull } from "@/lib/datetime";
import { PageHeader } from "@/components/shared/PageHeader";
import { StatCard } from "@/components/admin/StatCard";
import { UsageBadge } from "@/components/admin/UsageBadge";
import { MemoryPreviewLink } from "@/components/admin/MemoryPreviewLink";
import {
  ACTIVITY_METRICS_HINT,
  ActivityMetricsCell,
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
import type { UserAnalyticsDetail } from "@/types/admin";

function errorMessage(err: unknown, fallback: string): string {
  const e = err as { response?: { data?: { detail?: string } }; message?: string };
  return e?.response?.data?.detail || e?.message || fallback;
}

function fmt(dt: string | null | undefined): string {
  if (!dt) return "—";
  return formatDateTimeFull(dt);
}

export default function UserDetailPage() {
  const params = useParams<{ groupId: string; hostname: string }>();
  const hostname = decodeURIComponent(params.hostname);
  const groupId = params.groupId;
  const { fetchUserAnalytics } = useUserAnalyticsApi();
  const [user, setUser] = useState<UserAnalyticsDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUser(await fetchUserAnalytics(hostname));
    } catch (err) {
      setError(errorMessage(err, "Falha ao carregar perfil do usuário"));
    } finally {
      setLoading(false);
    }
  }, [fetchUserAnalytics, hostname]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <Link
        href={`/admin/users/${groupId}`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200"
      >
        <ArrowLeft className="h-4 w-4" /> Voltar ao grupo
      </Link>

      <PageHeader
        className="mb-4"
        icon={User}
        title={hostname}
        description={
          user?.group_name
            ? `Grupo: ${user.group_name} — perfil de uso da memória`
            : "Perfil de uso da memória compartilhada"
        }
      />

      {error && (
        <p className="mb-3 text-sm text-red-400" role="alert">
          {error}
        </p>
      )}

      {loading && !user ? (
        <p className="text-zinc-500">Carregando…</p>
      ) : user ? (
        <>
          <div className="mb-4 flex items-center gap-3">
            <UsageBadge level={user.usage_level} />
            <span className="text-sm text-zinc-400">
              Última gravação: {fmt(user.last_write_at)} · Última leitura:{" "}
              {fmt(user.last_read_at)}
            </span>
          </div>

          <p className="mb-2 text-xs text-zinc-500">
            Métricas no formato {ACTIVITY_METRICS_HINT}
          </p>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-3">
            <StatCard
              title="Escritas"
              value={
                <ActivityMetricsCell
                  h24={user.writes_24h}
                  d7={user.writes_7d}
                  total={user.writes_total}
                />
              }
              hint={ACTIVITY_METRICS_HINT}
            />
            <StatCard
              title="Leituras"
              value={
                <ActivityMetricsCell
                  h24={user.reads_24h}
                  d7={user.reads_7d}
                  total={user.reads_total}
                />
              }
              hint={ACTIVITY_METRICS_HINT}
            />
            <StatCard
              title="Memórias lidas (total)"
              value={user.distinct_memories_read}
              hint={`${user.distinct_projects_read} projetos · ${user.distinct_projects_written} gravados`}
            />
          </div>

          <h2 className="mb-3 text-lg font-semibold text-white">
            Gravações recentes
          </h2>
          <div className="mb-6 rounded-md border border-zinc-800">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Prévia</TableHead>
                  <TableHead>Projeto</TableHead>
                  <TableHead>Cliente</TableHead>
                  <TableHead>Data</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {user.recent_writes.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="py-6 text-center text-zinc-500">
                      Nenhuma gravação registrada
                    </TableCell>
                  </TableRow>
                ) : (
                  user.recent_writes.map((w) => (
                    <TableRow key={w.id}>
                      <TableCell>
                        <MemoryPreviewLink
                          preview={w.text_preview}
                          fullText={w.text}
                          project={w.project}
                          dialogTitle="Texto enviado para gravação"
                        />
                      </TableCell>
                      <TableCell>{w.project}</TableCell>
                      <TableCell className="text-zinc-400">
                        {w.client_name || "—"}
                      </TableCell>
                      <TableCell className="text-zinc-400">
                        {fmt(w.created_at)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          <h2 className="mb-3 text-lg font-semibold text-white">
            Leituras recentes
          </h2>
          <div className="rounded-md border border-zinc-800">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Prévia</TableHead>
                  <TableHead>Projeto</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead>Fonte</TableHead>
                  <TableHead>Data</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {user.recent_reads.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="py-6 text-center text-zinc-500">
                      Nenhuma leitura registrada
                    </TableCell>
                  </TableRow>
                ) : (
                  user.recent_reads.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell>
                        <MemoryPreviewLink
                          preview={r.memory_preview}
                          fullText={r.memory_text}
                          project={r.project}
                          memoryId={r.memory_id}
                          dialogTitle="Memória acessada"
                        />
                      </TableCell>
                      <TableCell>{r.project}</TableCell>
                      <TableCell className="text-zinc-400">{r.access_type}</TableCell>
                      <TableCell className="text-zinc-400">{r.source}</TableCell>
                      <TableCell className="text-zinc-400">
                        {fmt(r.accessed_at)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </>
      ) : null}
    </div>
  );
}
