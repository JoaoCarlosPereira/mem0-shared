import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface BackupPolicy {
  enabled: boolean;
  frequency: "daily" | "weekly";
  run_at: string;
  timezone: string;
  local_dir: string;
  retention: number;
  mirror_s3: boolean;
}

export interface BackupArchiveInfo {
  name: string;
  created_at: string | null;
  size: number;
  points_count: number | null;
  location: string;
}

export interface BackupProgress {
  operation: "backup" | "restore";
  phase: string | null;
  percent: number;
  started_at: string | null;
  finished_at: string | null;
  ok: boolean | null;
  error: string | null;
}

export interface BackupStatus {
  last_backup: string | null;
  rpo_age_seconds: number | null;
  archives: number;
  last_error: string | null;
  progress?: BackupProgress | null;
}

interface BackupState {
  status: BackupStatus | null;
  archives: BackupArchiveInfo[];
  policy: BackupPolicy | null;
  loading: boolean;
  error: string | null;
  restoring: boolean;
  restoreMessage: string | null;
  progress: BackupProgress | null;
}

const initialState: BackupState = {
  status: null,
  archives: [],
  policy: null,
  loading: false,
  error: null,
  restoring: false,
  restoreMessage: null,
  progress: null,
};

const backupSlice = createSlice({
  name: "backup",
  initialState,
  reducers: {
    setBackupStatus: (state, action: PayloadAction<BackupStatus>) => {
      state.status = action.payload;
      state.loading = false;
      // Worker único: só existe uma operação de backup/restore de cada vez.
      state.progress = action.payload.progress ?? null;
      // Polling de status não deve apagar o erro da operação que acabou de falhar.
      // Um novo backup/restore ou uma ação explícita limpa esse estado.
      if (action.payload.progress?.ok !== false && !action.payload.last_error) {
        state.error = null;
      }
    },
    setBackupList: (state, action: PayloadAction<BackupArchiveInfo[]>) => {
      state.archives = action.payload;
    },
    setBackupPolicy: (state, action: PayloadAction<BackupPolicy>) => {
      state.policy = action.payload;
      state.loading = false;
      state.error = null;
    },
    setBackupLoading: (state) => {
      state.loading = true;
      state.error = null;
    },
    setBackupError: (state, action: PayloadAction<string>) => {
      state.loading = false;
      state.error = action.payload;
    },
    setRestoring: (state, action: PayloadAction<boolean>) => {
      state.restoring = action.payload;
      if (action.payload) {
        state.restoreMessage = null;
        state.error = null;
      }
    },
    setRestoreMessage: (state, action: PayloadAction<string>) => {
      state.restoring = false;
      state.restoreMessage = action.payload;
    },
  },
});

export const {
  setBackupStatus,
  setBackupList,
  setBackupPolicy,
  setBackupLoading,
  setBackupError,
  setRestoring,
  setRestoreMessage,
} = backupSlice.actions;

export default backupSlice.reducer;
