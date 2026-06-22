// Tipos do domínio admin — espelham os schemas Pydantic do backend
// (openmemory/api/app/schemas.py: WriteQueueJobResponse, GovernanceJobResponse,
// AdminOverviewResponse e respostas paginadas). task_04 / ADR-002.
//
// Convenções: timestamps são `string` (ISO 8601); campos anuláveis usam
// `string | null` (espelhando `Optional[...]` do backend); enums são union
// literals de string (não `enum` TS), consistente com o restante do projeto.

export type WriteQueueStatus =
  | "queued"
  | "processing"
  | "done"
  | "skipped"
  | "failed";

export type GovernanceJobStatus = "queued" | "processing" | "done" | "failed";

export type GovernanceJobType =
  | "dedup"
  | "ttl_prune"
  | "consolidate"
  | "purge"
  | "enforce_quota"
  | "cold_tier";

// Espelha WriteQueueJobResponse
export type WriteQueueJob = {
  id: string;
  project: string;
  hostname: string;
  client_name: string | null;
  text_preview: string;
  status: WriteQueueStatus;
  error: string | null;
  attempts: number;
  created_at: string; // ISO 8601
};

// Espelha GovernanceJobResponse
export type GovernanceJob = {
  id: string;
  job_type: GovernanceJobType;
  project: string | null;
  status: GovernanceJobStatus;
  attempts: number;
  error: string | null;
  created_at: string;
  updated_at: string;
};

// Espelha WriteAuditLogResponse
export type WriteAuditLog = {
  id: string;
  job_id: string | null;
  project: string;
  hostname: string;
  client_name: string | null;
  action: string;
  created_at: string;
};

// Espelha AdminOverviewResponse
export type AdminOverview = {
  total_projects: number;
  total_memories: number;
  memories_last_24h: number;
  write_queue_queued: number;
  write_queue_processing: number;
  write_queue_done: number;
  write_queue_skipped: number;
  write_queue_failed: number;
  governance_queue_queued: number;
  governance_queue_processing: number;
  governance_queue_failed: number;
};

// Espelha PaginatedWriteQueueResponse
export type PaginatedWriteQueue = {
  items: WriteQueueJob[];
  total: number;
  page: number;
  pages: number;
  failed_count: number;
};

// Espelha PaginatedGovernanceJobResponse
export type PaginatedGovernanceQueue = {
  items: GovernanceJob[];
  total: number;
  page: number;
  pages: number;
  failed_count: number;
};

// Espelha PaginatedWriteAuditResponse
export type PaginatedWriteAudit = {
  items: WriteAuditLog[];
  total: number;
  page: number;
  pages: number;
};

// Filtros usados pelo queuesSlice / hooks de fila
export type WriteQueueFilter = {
  status?: WriteQueueStatus;
  project?: string;
  page: number;
};

export type GovernanceFilter = {
  status?: GovernanceJobStatus;
  job_type?: GovernanceJobType;
  project?: string;
  page: number;
};

// Item de /admin/projects/sizes (endpoint existente reutilizado pelo admin)
export type ProjectSize = {
  name: string;
  memory_count: number;
  partition_tier: "shared" | "dedicated";
  shard_key: string | null;
  over_threshold: boolean;
  last_activity_at?: string | null;
};

export type ProjectSizesResponse = {
  threshold: number;
  over_threshold_count: number;
  projects: ProjectSize[];
};

// Memória de um projeto lida do store vetorial (Qdrant) via
// GET /admin/projects/{project}/memories — fonte do MCP, indexada por projeto.
export type ProjectMemory = {
  id: string;
  memory: string | null;
  created_at: string | null;
  project: string | null;
  score?: number | null;
};

export type ProjectMemoriesResponse = {
  project: string;
  items: ProjectMemory[];
  total: number;
};

// Filtros da página de audit (estado local, não-Redux)
export type WriteAuditFilter = {
  project?: string;
  hostname?: string;
  from_date?: string;
  to_date?: string;
  page: number;
};
