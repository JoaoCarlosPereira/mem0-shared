import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import type { RootState } from "./store";
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
}

const initialState: QueuesState = {
  writeQueue: null,
  governanceQueue: null,
  writeQueueFilter: { page: 1 },
  governanceFilter: { page: 1 },
  loading: false,
  error: null,
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
  },
});

export const {
  setWriteQueue,
  setGovernanceQueue,
  setQueuesLoading,
  setQueuesError,
  setWriteQueueFilter,
  setGovernanceFilter,
} = queuesSlice.actions;

/**
 * Soma de jobs failed nas duas filas — lido pelo badge da AdminSidebar.
 * Independe de uma request dedicada: os módulos de fila já carregam
 * `failed_count` em cada response paginada.
 */
export const selectFailedCount = (state: RootState): number =>
  (state.queues.writeQueue?.failed_count ?? 0) +
  (state.queues.governanceQueue?.failed_count ?? 0);

export default queuesSlice.reducer;
