// Types da seção de Métricas de Tokens (task_04) — espelham os Pydantic
// schemas de openmemory/api/app/routers/metrics.py.

export type Granularity = "project" | "agent" | "user" | "model";

export type SortBy =
  | "created_at"
  | "total_tokens"
  | "input_tokens"
  | "output_tokens"
  | "duration_ms";

export type SortOrder = "asc" | "desc";

export interface MetricsFilters {
  start: string; // ISO 8601 (obrigatório na API)
  end?: string;
  granularity: Granularity;
  operation_type?: string[];
  project?: string;
  agent?: string;
  user_id?: string;
  model?: string;
}

export interface TokenSummaryRow {
  period: string; // YYYY-MM-DD
  group: string; // valor da dimensão selecionada (projeto, agente, ...)
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  operation_count: number;
  avg_tokens_per_op: number;
}

export interface TokenSummaryResponse {
  granularity: Granularity;
  data: TokenSummaryRow[];
}

export interface TokenUsageDetail {
  id: string;
  created_at: string | null;
  project: string;
  agent: string;
  user_id: string;
  operation_type: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  duration_ms: number | null;
  success: boolean;
  error: string | null;
  trace_id: string | null;
}

export interface TokenDetailsResponse {
  total: number;
  page: number;
  page_size: number;
  data: TokenUsageDetail[];
}
