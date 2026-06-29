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

export interface BackupStatus {
  last_backup: string | null;
  rpo_age_seconds: number | null;
  archives: number;
  last_error: string | null;
}

interface BackupState {
  status: BackupStatus | null;
  archives: BackupArchiveInfo[];
  policy: BackupPolicy | null;
  loading: boolean;
  error: string | null;
}

const initialState: BackupState = {
  status: null,
  archives: [],
  policy: null,
  loading: false,
  error: null,
};

const backupSlice = createSlice({
  name: "backup",
  initialState,
  reducers: {
    setBackupStatus: (state, action: PayloadAction<BackupStatus>) => {
      state.status = action.payload;
      state.loading = false;
      state.error = null;
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
  },
});

export const {
  setBackupStatus,
  setBackupList,
  setBackupPolicy,
  setBackupLoading,
  setBackupError,
} = backupSlice.actions;

export default backupSlice.reducer;
