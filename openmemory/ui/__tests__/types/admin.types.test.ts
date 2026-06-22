import type {
  AdminOverview,
  WriteQueueJob,
  GovernanceJob,
  PaginatedWriteQueue,
} from "@/types/admin";

// Estes testes validam o contrato de tipos em tempo de compilação (tsc/ts-jest).
// As linhas com @ts-expect-error FALHAM o build se o erro de tipo esperado
// deixar de ocorrer — garantindo que os union literals estão corretos.

describe("tipos admin", () => {
  it("aceita atribuição de objeto literal completo a WriteQueueJob", () => {
    const job: WriteQueueJob = {
      id: "1",
      project: "proj",
      hostname: "host",
      client_name: null, // null permitido
      text_preview: "abc",
      status: "queued",
      error: null,
      attempts: 0,
      created_at: "2026-01-01T00:00:00Z",
    };
    expect(job.status).toBe("queued");
  });

  it("rejeita status inválido (union literal)", () => {
    // @ts-expect-error 'invalid' não é um WriteQueueStatus
    const bad: WriteQueueJob["status"] = "invalid";
    expect(bad).toBe("invalid");
  });

  it("AdminOverview compila com todos os campos em zero", () => {
    const overview: AdminOverview = {
      total_projects: 0,
      total_memories: 0,
      memories_last_24h: 0,
      write_queue_queued: 0,
      write_queue_processing: 0,
      write_queue_done: 0,
      write_queue_skipped: 0,
      write_queue_failed: 0,
      governance_queue_queued: 0,
      governance_queue_processing: 0,
      governance_queue_failed: 0,
    };
    expect(overview.total_projects).toBe(0);
  });

  it("PaginatedWriteQueue inclui failed_count e items tipados", () => {
    const page: PaginatedWriteQueue = {
      items: [],
      total: 0,
      page: 1,
      pages: 0,
      failed_count: 0,
    };
    expect(page.failed_count).toBe(0);
  });

  it("GovernanceJob aceita project null e job_type literal", () => {
    const gj: GovernanceJob = {
      id: "1",
      job_type: "dedup",
      project: null,
      status: "queued",
      attempts: 0,
      error: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    expect(gj.project).toBeNull();
  });
});
