import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { renderHook, act } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

import metricsReducer from "@/store/metricsSlice";
import { useMetricsApi } from "@/hooks/useMetricsApi";
import type {
  MetricsFilters,
  TokenDetailsResponse,
  TokenSummaryResponse,
} from "@/types/metrics";

const filters: MetricsFilters = {
  start: "2026-06-01T00:00:00",
  end: "2026-06-30T23:59:59",
  granularity: "project",
  project: "proj-a",
};

const summaryResponse: TokenSummaryResponse = {
  granularity: "project",
  data: [
    {
      period: "2026-06-01",
      group: "proj-a",
      input_tokens: 100,
      output_tokens: 40,
      total_tokens: 140,
      operation_count: 2,
      avg_tokens_per_op: 70,
    },
  ],
};

const detailsResponse: TokenDetailsResponse = {
  total: 1,
  page: 1,
  page_size: 50,
  data: [
    {
      id: "abc",
      created_at: "2026-06-01T10:00:00",
      project: "proj-a",
      agent: "claude",
      user_id: "host-1",
      operation_type: "add",
      model: "qwen3",
      input_tokens: 100,
      output_tokens: 40,
      total_tokens: 140,
      cache_read_tokens: 0,
      cache_write_tokens: 0,
      duration_ms: 800,
      success: true,
      error: null,
      trace_id: null,
    },
  ],
};

function makeStore() {
  return configureStore({ reducer: { metrics: metricsReducer } });
}

function wrapperFor(store: ReturnType<typeof makeStore>) {
  return ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
}

beforeEach(() => {
  mockedAxios.get.mockReset();
});

describe("useMetricsApi", () => {
  it("fetchSummary faz GET /tokens/summary com filtros e despacha para o slice", async () => {
    mockedAxios.get.mockResolvedValue({ data: summaryResponse });
    const store = makeStore();
    const { result } = renderHook(() => useMetricsApi(), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchSummary(filters);
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/metrics/tokens/summary"),
      expect.objectContaining({
        params: expect.objectContaining({
          start: filters.start,
          project: "proj-a",
          granularity: "project",
        }),
      }),
    );
    expect(store.getState().metrics.summary).toEqual(summaryResponse);
    expect(store.getState().metrics.loading).toBe(false);
    expect(store.getState().metrics.error).toBeNull();
  });

  it("fetchSummary despacha erro quando a API falha", async () => {
    mockedAxios.get.mockRejectedValue(new Error("network down"));
    const store = makeStore();
    const { result } = renderHook(() => useMetricsApi(), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      const res = await result.current.fetchSummary(filters);
      expect(res).toBeNull();
    });

    expect(store.getState().metrics.error).toBe("network down");
    expect(store.getState().metrics.loading).toBe(false);
  });

  it("fetchDetails envia paginação/ordenação e despacha dados paginados", async () => {
    mockedAxios.get.mockResolvedValue({ data: detailsResponse });
    const store = makeStore();
    const { result } = renderHook(() => useMetricsApi(), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchDetails(filters, {
        page: 2,
        pageSize: 25,
        sortBy: "total_tokens",
        sortOrder: "asc",
      });
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/metrics/tokens/details"),
      expect.objectContaining({
        params: expect.objectContaining({
          page: 2,
          page_size: 25,
          sort_by: "total_tokens",
          sort_order: "asc",
        }),
      }),
    );
    expect(store.getState().metrics.details).toEqual(detailsResponse);
  });

  it("callbacks são estáveis entre renders (useCallback)", () => {
    const store = makeStore();
    const { result, rerender } = renderHook(() => useMetricsApi(), {
      wrapper: wrapperFor(store),
    });
    const first = {
      fetchSummary: result.current.fetchSummary,
      fetchDetails: result.current.fetchDetails,
      exportCsv: result.current.exportCsv,
    };
    rerender();
    expect(result.current.fetchSummary).toBe(first.fetchSummary);
    expect(result.current.fetchDetails).toBe(first.fetchDetails);
    expect(result.current.exportCsv).toBe(first.exportCsv);
  });
});
