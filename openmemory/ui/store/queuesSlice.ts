import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "./store";
import {
  countUnacknowledgedForKind,
} from "@/lib/queue-ui-prefs";
import {
  PaginatedWriteQueue,
  PaginatedGovernanceQueue,
  WriteQueueFilter,
  GovernanceFilter,
} from "@/types/admin";

interface QueuesState {
  writeQueue: PaginatedWriteQueue | null;
  governanceQueue: PaginatedGovernanceQueue | null;
  writeQueueFilter: WriteQueueFilter;
  governanceFilter: GovernanceFilter;
  loading: boolean;
  error: string | null;
  /** IDs de jobs failed (atualizados pelo polling — usados no badge da sidebar). */
  failedWriteJobIds: string[];
  failedGovernanceJobIds: string[];
  /** Incrementado quando prefs locais mudam (localStorage). */
  uiPrefsVersion: number;
}

const initialState: QueuesState = {
  writeQueue: null,
  governanceQueue: null,
  writeQueueFilter: { page: 1 },
  governanceFilter: { page: 1 },
  loading: false,
  error: null,
  failedWriteJobIds: [],
  failedGovernanceJobIds: [],
  uiPrefsVersion: 0,
};

const queuesSlice = createSlice({
  name: "queues",
  initialState,
  reducers: {
    setWriteQueue: (state, action: PayloadAction<PaginatedWriteQueue>) => {
      state.writeQueue = action.payload;
      state.loading = false;
      state.error = null;
    },
    setGovernanceQueue: (
      state,
      action: PayloadAction<PaginatedGovernanceQueue>,
    ) => {
      state.governanceQueue = action.payload;
      state.loading = false;
      state.error = null;
    },
    setQueuesLoading: (state) => {
      state.loading = true;
      state.error = null;
    },
    setQueuesError: (state, action: PayloadAction<string>) => {
      state.loading = false;
      state.error = action.payload;
    },
    setWriteQueueFilter: (
      state,
      action: PayloadAction<Partial<WriteQueueFilter>>,
    ) => {
      state.writeQueueFilter = { ...state.writeQueueFilter, ...action.payload };
    },
    setGovernanceFilter: (
      state,
      action: PayloadAction<Partial<GovernanceFilter>>,
    ) => {
      state.governanceFilter = {
        ...state.governanceFilter,
        ...action.payload,
      };
    },
    setFailedJobIds: (
      state,
      action: PayloadAction<{ write: string[]; governance: string[] }>,
    ) => {
      state.failedWriteJobIds = action.payload.write;
      state.failedGovernanceJobIds = action.payload.governance;
    },
    bumpQueueUiPrefs: (state) => {
      state.uiPrefsVersion += 1;
    },
  },
});

export const {
  setWriteQueue,
  setGovernanceQueue,
  setQueuesLoading,
  setQueuesError,
  setWriteQueueFilter,
  setGovernanceFilter,
  setFailedJobIds,
  bumpQueueUiPrefs,
} = queuesSlice.actions;

export type UnacknowledgedFailedCounts = {
  write: number;
  governance: number;
  total: number;
};

/**
 * Falhas ainda não reconhecidas (localStorage), por fila.
 * Usado na sidebar, Visão Geral e contadores da página Filas.
 */
export const selectUnacknowledgedFailedByKind = (
  state: RootState,
): UnacknowledgedFailedCounts => {
  void state.queues.uiPrefsVersion;
  if (typeof window === "undefined") {
    return { write: 0, governance: 0, total: 0 };
  }
  const write = countUnacknowledgedForKind(
    state.queues.failedWriteJobIds,
    "write",
  );
  const governance = countUnacknowledgedForKind(
    state.queues.failedGovernanceJobIds,
    "governance",
  );
  return { write, governance, total: write + governance };
};

/** Jobs failed ainda não vistos — alimenta o badge da sidebar. */
export const selectSidebarFailedCount = (state: RootState): number =>
  selectUnacknowledgedFailedByKind(state).total;

/** @deprecated Use selectSidebarFailedCount — mantido para testes legados. */
export const selectFailedCount = (state: RootState): number =>
  (state.queues.writeQueue?.failed_count ?? 0) +
  (state.queues.governanceQueue?.failed_count ?? 0);

export default queuesSlice.reducer;
