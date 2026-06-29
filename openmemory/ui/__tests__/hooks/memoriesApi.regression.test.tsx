import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { renderHook, act } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

import profileReducer from "@/store/profileSlice";
import memoriesReducer from "@/store/memoriesSlice";
import { useMemoriesApi } from "@/hooks/useMemoriesApi";
import { useStats } from "@/hooks/useStats";

function makeStore() {
  return configureStore({
    reducer: { profile: profileReducer, memories: memoriesReducer },
  });
}

function wrapperFor(store: ReturnType<typeof makeStore>) {
  return ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
}

beforeEach(() => {
  mockedAxios.get.mockReset();
  mockedAxios.post.mockReset();
  mockedAxios.get.mockImplementation((url: string) => {
    if (url.includes("/deletion-policy")) {
      return Promise.resolve({
        data: {
          memory_delete_allowed: true,
          bulk_delete_allowed: true,
          message: "ok",
        },
      });
    }
    return Promise.reject(new Error(`unexpected GET ${url}`));
  });
});

describe("useMemoriesApi regression", () => {
  it("fetchMemories usa POST /api/v1/memories/shared-filter com source shared", async () => {
    mockedAxios.post.mockResolvedValue({
      data: {
        items: [
          {
            id: "abc",
            content: "fact",
            created_at: "2026-06-21T00:00:00+00:00",
            state: "active",
            app_name: "sysmovs",
            categories: [],
          },
        ],
        total: 1,
        pages: 1,
      },
    });
    const store = makeStore();
    const { result } = renderHook(() => useMemoriesApi(), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      const out = await result.current.fetchMemories("", 1, 10);
      expect(out.total).toBe(1);
    });

    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/memories/shared-filter"),
      expect.objectContaining({ source: "shared", user_id: "user" }),
    );
    expect(mockedAxios.post.mock.calls[0][0]).toMatch(/^\/api-proxy|http/);
  });

  it("deleteMemories usa POST /actions/delete", async () => {
    mockedAxios.post.mockImplementation((url: string) => {
      if (url.includes("/actions/delete")) {
        return Promise.resolve({ data: { message: "ok" } });
      }
      return Promise.reject(new Error(`unexpected POST ${url}`));
    });
    const store = makeStore();
    const { result } = renderHook(() => useMemoriesApi(), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.deleteMemories(["abc-def"]);
    });

    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/memories/actions/delete"),
      { memory_ids: ["abc-def"], user_id: "user" },
    );
  });
});

describe("useStats regression", () => {
  it("fetchStats usa trailing slash em /api/v1/stats/", async () => {
    mockedAxios.get.mockResolvedValue({
      data: { total_memories: 525, total_apps: 1, apps: [] },
    });
    const store = makeStore();
    const { result } = renderHook(() => useStats(), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchStats();
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/v1\/stats\/\?user_id=/),
    );
    expect(store.getState().profile.totalMemories).toBe(525);
  });
});
