import { createSlice, PayloadAction } from "@reduxjs/toolkit";
import {
  TokenDetailsResponse,
  TokenSummaryResponse,
} from "@/types/metrics";

interface MetricsState {
  summary: TokenSummaryResponse | null;
  details: TokenDetailsResponse | null;
  loading: boolean;
  error: string | null;
}

const initialState: MetricsState = {
  summary: null,
  details: null,
  loading: false,
  error: null,
};

const metricsSlice = createSlice({
  name: "metrics",
  initialState,
  reducers: {
    setMetricsLoading: (state) => {
      state.loading = true;
      state.error = null;
    },
    setMetricsError: (state, action: PayloadAction<string>) => {
      state.loading = false;
      state.error = action.payload;
    },
    setSummaryData: (state, action: PayloadAction<TokenSummaryResponse>) => {
      state.summary = action.payload;
      state.loading = false;
      state.error = null;
    },
    setDetailsData: (state, action: PayloadAction<TokenDetailsResponse>) => {
      state.details = action.payload;
      state.loading = false;
      state.error = null;
    },
  },
});

export const {
  setMetricsLoading,
  setMetricsError,
  setSummaryData,
  setDetailsData,
} = metricsSlice.actions;

export default metricsSlice.reducer;
