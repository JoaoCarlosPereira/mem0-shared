import { useEffect, useState } from "react";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { resolveAttribution } from "@/lib/attribution";
import { CreatorAvatar } from "@/components/shared/creator-avatar";
import { useSelector } from "react-redux";
import { RootState } from "@/store/store";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatDateTime } from "@/lib/i18n/pt-BR";

interface AccessLogEntry {
  id: string;
  app_name: string;
  display_name?: string;
  avatar_url?: string;
  client_name?: string;
  hostname?: string;
  accessed_at: string;
}

interface AccessLogProps {
  memoryId: string;
}

export function AccessLog({ memoryId }: AccessLogProps) {
  const { fetchAccessLogs } = useMemoriesApi();
  const accessEntries = useSelector(
    (state: RootState) => state.memories.accessLogs
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadAccessLogs = async () => {
      try {
        await fetchAccessLogs(memoryId);
      } catch (error) {
        console.error("Failed to fetch access logs:", error);
      } finally {
        setIsLoading(false);
      }
    };

    loadAccessLogs();
  }, []);

  if (isLoading) {
    return (
      <div className="w-full max-w-md mx-auto rounded-3xl overflow-hidden bg-[#1c1c1c] text-white p-6">
        <p className="text-center text-zinc-500">Carregando logs de acesso...</p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md mx-auto rounded-lg overflow-hidden bg-zinc-900 border border-zinc-800 text-white pb-1">
      <div className="px-6 py-4 flex justify-between items-center bg-zinc-800 border-b border-zinc-800">
        <h2 className="font-semibold">Log de Acesso</h2>
      </div>

      <ScrollArea className="p-6 max-h-[450px]">
        {accessEntries.length === 0 && (
          <div className="w-full max-w-md mx-auto rounded-3xl overflow-hidden min-h-[110px] flex items-center justify-center text-white p-6">
            <p className="text-center text-zinc-500">
              Nenhum log de acesso disponível
            </p>
          </div>
        )}
        <ul className="space-y-8">
          {accessEntries.map((entry: AccessLogEntry, index: number) => {
            const attribution = resolveAttribution({
              appName: entry.app_name,
              clientName: entry.client_name,
              hostname: entry.hostname,
              displayName: entry.display_name,
              avatarUrl: entry.avatar_url,
            });
            const label = attribution.label;

            return (
              <li key={entry.id} className="relative flex items-start gap-4">
                <div className="relative z-10 rounded-full overflow-hidden bg-[#2a2a2a] w-8 h-8 flex items-center justify-center flex-shrink-0">
                  <CreatorAvatar
                    attribution={attribution}
                    size={32}
                    className="w-8 h-8"
                  />
                </div>

                {index < accessEntries.length - 1 && (
                  <div className="absolute left-4 top-6 bottom-0 w-[1px] h-[calc(100%+1rem)] bg-[#333333] transform -translate-x-1/2"></div>
                )}

                <div className="flex flex-col">
                  <span className="font-medium">{label}</span>
                  <span className="text-zinc-400 text-sm">
                    {formatDateTime(entry.accessed_at)}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      </ScrollArea>
    </div>
  );
}
