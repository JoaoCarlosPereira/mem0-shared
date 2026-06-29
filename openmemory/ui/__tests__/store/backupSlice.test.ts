import backupReducer, {
  setBackupStatus,
  setBackupPolicy,
  setBackupList,
  setBackupError,
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

  it("setBackupPolicy popula a política", () => {
    const state = backupReducer(undefined, setBackupPolicy(policy));
    expect(state.policy?.frequency).toBe("weekly");
    expect(state.policy?.retention).toBe(7);
  });

  it("setBackupList substitui a lista de cópias", () => {
    const archives: BackupArchiveInfo[] = [
      { name: "a.zip", created_at: null, size: 1, points_count: 6, location: "local" },
    ];
    const state = backupReducer(undefined, setBackupList(archives));
    expect(state.archives).toHaveLength(1);
  });

  it("setBackupError registra a mensagem de erro", () => {
    const state = backupReducer(undefined, setBackupError("boom"));
    expect(state.error).toBe("boom");
    expect(state.loading).toBe(false);
  });
});
