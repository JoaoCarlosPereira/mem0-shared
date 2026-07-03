"use client";

import { useState } from "react";
import { Granularity, MetricsFilters } from "@/types/metrics";

interface TokenFiltersProps {
  filters: MetricsFilters;
  onChange: (filters: MetricsFilters) => void;
}

const GRANULARITIES: { value: Granularity; label: string }[] = [
  { value: "project", label: "Projeto" },
  { value: "agent", label: "Agente" },
  { value: "user", label: "Usuário" },
  { value: "model", label: "Modelo" },
];

const OPERATION_TYPES = [
  { value: "", label: "Todas as operações" },
  { value: "add", label: "Extração (add)" },
  { value: "search", label: "Busca (search)" },
  { value: "update", label: "Atualização (update)" },
  { value: "embed", label: "Embedding" },
];

const inputCls =
  "h-9 rounded-md border border-zinc-800 bg-zinc-950 px-2 text-sm text-zinc-200 " +
  "placeholder:text-zinc-600 focus:border-zinc-600 focus:outline-none";

/** Converte "YYYY-MM-DD" do input date para o ISO esperado pela API. */
function toStartIso(date: string): string {
  return date ? `${date}T00:00:00` : "";
}

function toEndIso(date: string): string | undefined {
  return date ? `${date}T23:59:59` : undefined;
}

function isoToDate(iso?: string): string {
  return iso ? iso.slice(0, 10) : "";
}

/**
 * Barra de filtros da seção de Métricas (task_05). Mantém um rascunho local e
 * só propaga no "Aplicar", evitando um fetch por tecla digitada.
 */
export function TokenFilters({ filters, onChange }: TokenFiltersProps) {
  const [draft, setDraft] = useState({
    start: isoToDate(filters.start),
    end: isoToDate(filters.end),
    granularity: filters.granularity,
    operationType: filters.operation_type?.[0] ?? "",
    project: filters.project ?? "",
    agent: filters.agent ?? "",
    userId: filters.user_id ?? "",
    model: filters.model ?? "",
  });

  const apply = () => {
    if (!draft.start) return;
    onChange({
      start: toStartIso(draft.start),
      end: toEndIso(draft.end),
      granularity: draft.granularity,
      operation_type: draft.operationType ? [draft.operationType] : undefined,
      project: draft.project.trim() || undefined,
      agent: draft.agent.trim() || undefined,
      user_id: draft.userId.trim() || undefined,
      model: draft.model.trim() || undefined,
    });
  };

  return (
    <div className="flex flex-wrap items-end gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Início
        <input
          type="date"
          required
          className={inputCls}
          value={draft.start}
          onChange={(e) => setDraft({ ...draft, start: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Fim
        <input
          type="date"
          className={inputCls}
          value={draft.end}
          onChange={(e) => setDraft({ ...draft, end: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Agrupar por
        <select
          className={inputCls}
          value={draft.granularity}
          onChange={(e) =>
            setDraft({ ...draft, granularity: e.target.value as Granularity })
          }
        >
          {GRANULARITIES.map((g) => (
            <option key={g.value} value={g.value}>
              {g.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Operação
        <select
          className={inputCls}
          value={draft.operationType}
          onChange={(e) => setDraft({ ...draft, operationType: e.target.value })}
        >
          {OPERATION_TYPES.map((op) => (
            <option key={op.value} value={op.value}>
              {op.label}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Projeto
        <input
          className={inputCls}
          placeholder="todos"
          value={draft.project}
          onChange={(e) => setDraft({ ...draft, project: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Agente
        <input
          className={inputCls}
          placeholder="todos"
          value={draft.agent}
          onChange={(e) => setDraft({ ...draft, agent: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Usuário
        <input
          className={inputCls}
          placeholder="todos"
          value={draft.userId}
          onChange={(e) => setDraft({ ...draft, userId: e.target.value })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-zinc-400">
        Modelo
        <input
          className={inputCls}
          placeholder="todos"
          value={draft.model}
          onChange={(e) => setDraft({ ...draft, model: e.target.value })}
        />
      </label>
      <button
        type="button"
        onClick={apply}
        className="h-9 rounded-md bg-violet-600 px-4 text-sm font-medium text-white hover:bg-violet-500"
      >
        Aplicar
      </button>
    </div>
  );
}
