import backupReducer, {
  setBackupStatus,
  setBackupPolicy,
  setBackupList,
  setBackupError,
  setRestoring,
  setRestoreMessage,
} from "@/store/backupSlice";
import type {
  BackupStatus,
  BackupPolicy,
  BackupArchiveInfo,
} from "@/store/backupSlice";

const status: BackupStatus = {
  last_backup: "20260618-030000.zip",
  rpo_age_seconds: 3600,
  archives: 3,
  last_error: null,
};

const policy: BackupPolicy = {
  enabled: true,
  frequency: "weekly",
  run_at: "02:30",
  timezone: "America/Sao_Paulo",
  local_dir: "/mnt/backups",
  retention: 7,
  mirror_s3: true,
};

describe("backupSlice", () => {
  it("estado inicial: status/policy null, archives vazio", () => {
    const state = backupReducer(undefined, { type: "@@INIT" });
    expect(state.status).toBeNull();
    expect(state.policy).toBeNull();
    expect(state.archives).toEqual([]);
  });

  it("setBackupStatus popula o status e limpa erro", () => {
    const state = backupReducer(undefined, setBackupStatus(status));
    expect(state.status).toEqual(status);
    expect(state.error).toBeNull();
  });

  it("setBackupStatus popula o progress da operação em andamento", () => {
    const backupProgress = {
      operation: "backup" as const,
      phase: "dump do PostgreSQL",
      percent: 50,
      started_at: null,
      finished_at: null,
      ok: null,
      error: null,
    };
    const state = backupReducer(
      undefined,
      setBackupStatus({ ...status, progress: backupProgress }),
    );
    expect(state.progress?.operation).toBe("backup");
    expect(state.progress?.percent).toBe(50);

    const restoreProgress = {
      operation: "restore" as const,
      phase: "restaurando Qdrant",
      percent: 70,
      started_at: null,
      finished_at: null,
      ok: null,
      error: null,
    };
    const next = backupReducer(state, setBackupStatus({ ...status, progress: restoreProgress }));
    expect(next.progress?.operation).toBe("restore");
    expect(next.progress?.percent).toBe(70);

    // sem progress (operação finalizada) → limpa
    const cleared = backupReducer(next, setBackupStatus({ ...status, progress: null }));
    expect(cleared.progress).toBeNull();
  });

  it("setBackupStatus preserva erro reportado pelo progresso durante o polling", () => {
    const failedProgress = {
      operation: "restore" as const,
      phase: "snapshot de segurança",
      percent: 10,
      started_at: null,
      finished_at: null,
      ok: false,
      error: "psql: timeout expired",
    };

    const state = backupReducer(undefined, setBackupError("psql: timeout expired"));
    const polled = backupReducer(
      state,
      setBackupStatus({ ...status, progress: failedProgress }),
    );

    expect(polled.error).toBe("psql: timeout expired");
    expect(polled.progress?.percent).toBe(10);
  });

  it("setBackupPolicy popula a política", () => {
    const state = backupReducer(undefined, setBackupPolicy(policy));
    expect(state.policy?.frequency).toBe("weekly");
    expect(state.policy?.retention).toBe(7);
  });

  it("setBackupList substitui a lista de cópias", () => {
    const archives: BackupArchiveInfo[] = [
      {
        name: "a.zip",
        created_at: null,
        size: 1,
        points_count: 6,
        location: "local",
        schema_version: 2,
        verification_status: "verified",
        restore_allowed: true,
        verification_error: null,
      },
    ];
    const state = backupReducer(undefined, setBackupList(archives));
    expect(state.archives).toHaveLength(1);
  });

  it("setBackupError registra a mensagem de erro", () => {
    const state = backupReducer(undefined, setBackupError("boom"));
    expect(state.error).toBe("boom");
    expect(state.loading).toBe(false);
  });

  it("setRestoring(true) ativa o estado de restauração e limpa mensagens", () => {
    const state = backupReducer(undefined, setRestoring(true));
    expect(state.restoring).toBe(true);
    expect(state.restoreMessage).toBeNull();
    expect(state.error).toBeNull();
  });

  it("setRestoreMessage finaliza a restauração e guarda a mensagem", () => {
    const state = backupReducer(undefined, setRestoreMessage("Restore concluído."));
    expect(state.restoring).toBe(false);
    expect(state.restoreMessage).toBe("Restore concluído.");
  });
});
