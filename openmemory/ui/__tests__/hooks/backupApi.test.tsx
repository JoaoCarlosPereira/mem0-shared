import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { renderHook, act } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

import adminReducer from "@/store/adminSlice";
import backupReducer from "@/store/backupSlice";
import type { BackupPolicy } from "@/store/backupSlice";
import { useBackupApi } from "@/hooks/useBackupApi";

const status = {
  last_backup: "20260618-030000.zip",
  rpo_age_seconds: 3600,
  archives: 3,
  last_error: null,
};

const policy: BackupPolicy = {
  enabled: true,
  frequency: "daily",
  run_at: "03:00",
  timezone: "America/Sao_Paulo",
  local_dir: "/mnt/backups",
  retention: 7,
  mirror_s3: false,
};

function makeStore() {
  return configureStore({
    reducer: { admin: adminReducer, backup: backupReducer },
  });
}

function wrapperFor(store: ReturnType<typeof makeStore>) {
  return ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
}

beforeEach(() => {
  mockedAxios.get.mockReset();
  mockedAxios.put.mockReset();
  mockedAxios.post.mockReset();
});

describe("useBackupApi", () => {
  it("fetchStatus faz GET /admin/backup/status e popula o slice", async () => {
    mockedAxios.get.mockResolvedValue({ data: status });
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.fetchStatus();
    });
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/backup/status"),
    );
    expect(store.getState().backup.status?.rpo_age_seconds).toBe(3600);
  });

  it("savePolicy válida faz PUT e atualiza o slice", async () => {
    mockedAxios.put.mockResolvedValue({ data: policy });
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.savePolicy(policy);
    });
    expect(ok).toBe(true);
    expect(mockedAxios.put).toHaveBeenCalledWith(
      expect.stringContaining("/admin/backup/policy"),
      policy,
    );
    expect(store.getState().backup.policy?.retention).toBe(7);
  });

  it("savePolicy com retenção inválida NÃO chama PUT e registra erro", async () => {
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.savePolicy({ ...policy, retention: 51 });
    });
    expect(ok).toBe(false);
    expect(mockedAxios.put).not.toHaveBeenCalled();
    expect(store.getState().backup.error).toMatch(/Reten/);
  });

  it("runBackup faz POST /admin/backup/run", async () => {
    mockedAxios.post.mockResolvedValue({ data: { status: "accepted" } });
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.runBackup();
    });
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/admin/backup/run"),
    );
  });

  it("restore faz POST /admin/backup/restore com archive e confirm", async () => {
    mockedAxios.post.mockResolvedValue({ data: { status: "accepted" } });
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.restore("20260618-030000.zip", "20260618-030000.zip");
    });
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/admin/backup/restore"),
      { archive: "20260618-030000.zip", confirm: "20260618-030000.zip" },
    );
  });
});
