"use client";

import { useState, useEffect } from "react";
import { useAdminApi } from "@/hooks/useAdminApi";
import { KanbanPrompt, KanbanPromptUpdate } from "@/types/admin";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { PageHeader } from "@/components/shared/PageHeader";
import { MessageSquare } from "lucide-react";

export default function KanbanPromptsPage() {
  const [prompts, setPrompts] = useState<KanbanPrompt[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingStatus, setSavingStatus] = useState<Record<string, "saving" | "saved" | "error">>({});
  const { fetchKanbanPrompts, updateKanbanPrompt } = useAdminApi();

  useEffect(() => {
    let active = true;
    fetchKanbanPrompts()
      .then((data) => {
        if (active) setPrompts(data);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function handleLocalUpdate(status: string, updates: KanbanPromptUpdate) {
    setPrompts(prev => prev.map(p => p.column_status === status ? { ...p, ...updates } : p));
  }

  async function handleUpdate(status: string, updates: KanbanPromptUpdate) {
    setSavingStatus(prev => ({ ...prev, [status]: "saving" }));
    try {
      const savedPrompt = await updateKanbanPrompt(status, updates);
      setPrompts(prev => prev.map(p => p.column_status === status ? savedPrompt : p));
      setSavingStatus(prev => ({ ...prev, [status]: "saved" }));
      setTimeout(() => {
        setSavingStatus(prev => {
          const next = { ...prev };
          delete next[status];
          return next;
        });
      }, 2000);
    } catch {
      setSavingStatus(prev => ({ ...prev, [status]: "error" }));
    }
  }

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-violet-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <PageHeader
        className="mb-4"
        icon={MessageSquare}
        title="Prompts de Coluna"
        description="Configure as instruções específicas para cada etapa do pipeline Kanban."
      />

      <div className="rounded-xl border border-slate-800 bg-slate-950/50 backdrop-blur-sm overflow-hidden">
        <Table>
          <TableHeader className="bg-slate-900/50">
            <TableRow>
              <TableHead className="text-slate-300">Column Status</TableHead>
              <TableHead className="text-slate-300">Label</TableHead>
              <TableHead className="text-slate-300 w-1/3">Prompt</TableHead>
              <TableHead className="text-slate-300 text-center">Ativado</TableHead>
              <TableHead className="text-slate-300">Última Atualização</TableHead>
              <TableHead className="text-slate-300">Atualizado Por</TableHead>
              <TableHead className="text-slate-300 w-20"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {prompts.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-slate-500">
                  Nenhum prompt configurado.
                </TableCell>
              </TableRow>
            ) : (
              prompts.map((prompt) => (
                <TableRow key={prompt.column_status} className="group">
                  <TableCell className="font-mono text-xs text-violet-400">
                    {prompt.column_status}
                  </TableCell>
                  <TableCell className="text-slate-300">
                    {prompt.label}
                  </TableCell>
                  <TableCell>
                    <div className="relative">
                      <Textarea
                        value={prompt.prompt || ""}
                        onChange={(e) => handleLocalUpdate(prompt.column_status, { prompt: e.target.value })}
                        onBlur={(e) => handleUpdate(prompt.column_status, { prompt: e.target.value })}
                        placeholder="Use o padrão COLUMN_GUIDE.do_now"
                        className={cn(
                          "min-h-[80px] bg-slate-900/50 border-slate-700 text-slate-200 placeholder:text-slate-600 focus:border-violet-500 transition-colors",
                          !prompt.prompt && "italic"
                        )}
                      />
                      {!prompt.prompt && (
                        <div className="absolute -top-2 -right-2">
                          <span className="flex items-center gap-1 rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-400 border border-slate-700">
                            <AlertCircle className="h-3 w-3" />
                            Padrão
                          </span>
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex justify-center">
                      <Switch
                        checked={prompt.is_enabled}
                        onCheckedChange={(checked) => handleUpdate(prompt.column_status, { is_enabled: checked })}
                      />
                    </div>
                  </TableCell>
                  <TableCell className="text-xs text-slate-500">
                    {prompt.updated_at ? new Date(prompt.updated_at).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell className="text-xs text-slate-500">
                    {prompt.updated_by || "—"}
                  </TableCell>
                  <TableCell>
                    <div className="flex justify-center">
                      {savingStatus[prompt.column_status] === "saving" && (
                        <Loader2 className="h-4 w-4 animate-spin text-violet-500" />
                      )}
                      {savingStatus[prompt.column_status] === "saved" && (
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      )}
                      {savingStatus[prompt.column_status] === "error" && (
                        <AlertCircle className="h-4 w-4 text-rose-500" />
                      )}
                    </div>
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
