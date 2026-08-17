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

  it("runBackup faz POST /admin/backup/run e espera a cópia", async () => {
    jest.useFakeTimers();
    mockedAxios.get
      .mockResolvedValueOnce({
        data: { ...status, archives: 0, last_backup: null },
      })
      .mockResolvedValueOnce({
        data: { ...status, archives: 1, last_backup: "20260618-030000.zip" },
      })
      .mockResolvedValue({ data: { archives: [] } }); // fetchList
    mockedAxios.post.mockResolvedValue({ data: { status: "accepted" } });
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let ok: boolean | undefined;
    await act(async () => {
      const pending = result.current.runBackup();
      await jest.advanceTimersByTimeAsync(3000);
      ok = await pending;
    });
    expect(ok).toBe(true);
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/admin/backup/run"),
    );
    expect(store.getState().backup.status?.archives).toBe(1);
    jest.useRealTimers();
  });

  it("restore faz POST /admin/backup/restore com archive e confirm e conclui quando o snapshot aparece", async () => {
    jest.useFakeTimers();
    mockedAxios.get
      .mockResolvedValueOnce({ data: { ...status, archives: 3, last_error: null } }) // before
      .mockResolvedValue({ data: { ...status, archives: 4, last_error: null } }); // poll: +1 (pre-restore)
    mockedAxios.post.mockResolvedValue({ data: { status: "accepted" } });
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let ok: boolean | undefined;
    await act(async () => {
      const pending = result.current.restore("20260618-030000.zip", "20260618-030000.zip");
      await jest.advanceTimersByTimeAsync(3000);
      ok = await pending;
    });
    expect(ok).toBe(true);
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/admin/backup/restore"),
      { archive: "20260618-030000.zip", confirm: "20260618-030000.zip" },
    );
    expect(store.getState().backup.restoring).toBe(false);
    expect(store.getState().backup.restoreMessage).toMatch(/concluído/);
    jest.useRealTimers();
  });

  it("restore em erro (4xx/5xx) registra erro e limpa o estado de restauração", async () => {
    mockedAxios.get.mockResolvedValue({ data: { ...status, archives: 3, last_error: null } });
    mockedAxios.post.mockRejectedValue(new Error("Falha ao restaurar backup"));
    const store = makeStore();
    const { result } = renderHook(() => useBackupApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let ok: boolean | undefined;
    await act(async () => {
      ok = await result.current.restore("20260618-030000.zip", "errado.zip");
    });
    expect(ok).toBe(false);
    expect(store.getState().backup.restoring).toBe(false);
    expect(store.getState().backup.error).toMatch(/Falha ao restaurar backup/);
  });
});
