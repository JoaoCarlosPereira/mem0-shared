import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import { AdminOverview } from "@/types/admin";

interface AdminState {
  overview: AdminOverview | null;
  pollingIntervalMs: number;
  loading: boolean;
  error: string | null;
}

const initialState: AdminState = {
  overview: null,
  // Padrão de 15s (PRD); configurável entre 10–60s.
  pollingIntervalMs: 15000,
  loading: false,
  error: null,
};

const adminSlice = createSlice({
  name: "admin",
  initialState,
  reducers: {
    setAdminOverview: (state, action: PayloadAction<AdminOverview>) => {
      state.overview = action.payload;
      state.loading = false;
      state.error = null;
    },
    setAdminLoading: (state) => {
      state.loading = true;
      state.error = null;
    },
    setAdminError: (state, action: PayloadAction<string>) => {
      state.loading = false;
      state.error = action.payload;
    },
    setPollingInterval: (state, action: PayloadAction<number>) => {
      // Mantém o intervalo dentro da faixa suportada (10–60s).
      const clamped = Math.min(60000, Math.max(10000, action.payload));
      state.pollingIntervalMs = clamped;
    },
  },
});

export const {
  setAdminOverview,
  setAdminLoading,
  setAdminError,
  setPollingInterval,
} = adminSlice.actions;

export default adminSlice.reducer;
