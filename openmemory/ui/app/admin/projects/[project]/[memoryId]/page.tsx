"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft } from "lucide-react";
import { resolveAttribution } from "@/lib/attribution";

export default function AdminMemoryDetailPage() {
  const params = useParams<{ project: string; memoryId: string }>();
  const { project, memoryId } = params;
  const projectName = decodeURIComponent(project);
  const { fetchMemoryById, fetchAccessLogs, isLoading } = useMemoriesApi();
  const memory = useSelector(
    (state: RootState) => state.memories.selectedMemory,
  );
  const accessLogs = useSelector(
    (state: RootState) => state.memories.accessLogs,
  );

  useEffect(() => {
    fetchMemoryById(memoryId).catch(() => {});
    fetchAccessLogs(memoryId).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memoryId]);

  return (
    <div className="max-w-3xl">
      <Link
        href={`/admin/projects/${encodeURIComponent(projectName)}`}
        className="mb-4 inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-200"
      >
        <ArrowLeft className="h-4 w-4" /> Voltar para {projectName}
      </Link>

      {isLoading && !memory ? (
        <Skeleton className="h-40 w-full rounded-lg" />
      ) : !memory ? (
        <p className="text-zinc-500">Memória não encontrada.</p>
      ) : (
        <div className="space-y-4">
          <Card className="border-zinc-800 bg-zinc-900">
            <CardHeader>
              <CardTitle className="text-zinc-100">Conteúdo</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="whitespace-pre-wrap text-zinc-200">
                {memory.text}
              </p>
            </CardContent>
          </Card>

          <Card className="border-zinc-800 bg-zinc-900">
            <CardHeader>
              <CardTitle className="text-zinc-100">Metadados</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm text-zinc-400">
              <div>ID: {memory.id}</div>
              <div>Estado: {memory.state}</div>
              <div>
                Criado por:{" "}
                {resolveAttribution({
                  appName: memory.app_name,
                  clientName: memory.created_by_client,
                  hostname: memory.created_by_hostname,
                  metadata: memory.metadata_,
                }).label}
              </div>
              <div>Categorias: {memory.categories?.join(", ") || "—"}</div>
              <div>Criado em: {memory.created_at}</div>
            </CardContent>
          </Card>

          <Card className="border-zinc-800 bg-zinc-900">
            <CardHeader>
              <CardTitle className="text-zinc-100">Últimos acessos</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-zinc-400">
              {accessLogs.length === 0 ? (
                <span className="text-zinc-600">Nenhum acesso registrado</span>
              ) : (
                <ul className="space-y-1">
                  {accessLogs.map((log) => (
                    <li key={log.id}>
                      {log.display_name ||
                        resolveAttribution({
                          appName: log.app_name,
                          clientName: log.client_name,
                          hostname: log.hostname,
                        }).label}{" "}
                      — {log.accessed_at}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
