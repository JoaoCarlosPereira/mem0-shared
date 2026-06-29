import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { renderHook, act } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

import adminReducer from "@/store/adminSlice";
import queuesReducer, { setWriteQueueFilter } from "@/store/queuesSlice";
import { useAdminApi } from "@/hooks/useAdminApi";
import { useQueuesApi } from "@/hooks/useQueuesApi";
import type { AdminOverview } from "@/types/admin";

const overview: AdminOverview = {
  total_projects: 1,
  total_memories: 1,
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

function makeStore() {
  return configureStore({
    reducer: { admin: adminReducer, queues: queuesReducer },
  });
}

function wrapperFor(store: ReturnType<typeof makeStore>) {
  return ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
}

beforeEach(() => {
  mockedAxios.get.mockReset();
});

describe("useAdminApi", () => {
  it("fetchAdminOverview faz GET /admin/overview e despacha para adminSlice", async () => {
    mockedAxios.get.mockResolvedValue({ data: overview });
    const store = makeStore();
    const { result } = renderHook(() => useAdminApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchAdminOverview();
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/overview"),
    );
    expect(store.getState().admin.overview).toEqual(overview);
  });

  it("erro 500 no overview não quebra o hook — despacha erro", async () => {
    mockedAxios.get.mockRejectedValue(new Error("Request failed 500"));
    const store = makeStore();
    const { result } = renderHook(() => useAdminApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchAdminOverview();
    });

    expect(store.getState().admin.error).toBe("Request failed 500");
    expect(store.getState().admin.overview).toBeNull();
  });

  it("fetchWriteAudit passa project=proj-x como query param", async () => {
    mockedAxios.get.mockResolvedValue({
      data: { items: [], total: 0, page: 1, pages: 0 },
    });
    const store = makeStore();
    const { result } = renderHook(() => useAdminApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchWriteAudit({ project: "proj-x", page: 1 });
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/write-audit"),
      expect.objectContaining({
        params: expect.objectContaining({ project: "proj-x", page: 1 }),
      }),
    );
  });

  it("polling dispara fetchAdminOverview ao montar e no intervalo", () => {
    jest.useFakeTimers();
    mockedAxios.get.mockResolvedValue({ data: overview });
    const store = makeStore();
    renderHook(() => useAdminApi(), { wrapper: wrapperFor(store) });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/overview"),
    );
    mockedAxios.get.mockClear();
    act(() => {
      jest.advanceTimersByTime(15000);
    });
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/overview"),
    );
    jest.useRealTimers();
  });
});

describe("useQueuesApi", () => {
  it("fetchWriteQueue faz GET /admin/write-queue com filtros do slice (status + page)", async () => {
    mockedAxios.get.mockResolvedValue({
      data: { items: [], total: 0, page: 2, pages: 0, failed_count: 0 },
    });
    const store = makeStore();
    store.dispatch(setWriteQueueFilter({ status: "failed", page: 2 }));

    const { result } = renderHook(() => useQueuesApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchWriteQueue();
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/write-queue"),
      expect.objectContaining({
        params: expect.objectContaining({ status: "failed", page: 2 }),
      }),
    );
  });

  it("fetchGovernanceJobs faz GET /admin/governance/jobs", async () => {
    mockedAxios.get.mockResolvedValue({
      data: { items: [], total: 0, page: 1, pages: 0, failed_count: 0 },
    });
    const store = makeStore();
    const { result } = renderHook(() => useQueuesApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchGovernanceJobs();
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/governance/jobs"),
      expect.anything(),
    );
  });

  it("erro 500 na write queue é tratado (não lança)", async () => {
    mockedAxios.get.mockRejectedValue(new Error("boom"));
    const store = makeStore();
    const { result } = renderHook(() => useQueuesApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchWriteQueue();
    });

    expect(store.getState().queues.error).toBe("boom");
  });
});
