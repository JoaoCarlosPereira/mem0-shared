import { useCallback } from "react";
import axios from "axios";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import {
  BackupPolicy,
  setBackupStatus,
  setBackupList,
  setBackupPolicy,
  setBackupLoading,
  setBackupError,
} from "@/store/backupSlice";
import { usePolling } from "@/hooks/usePolling";
import { isValidRetention } from "@/lib/backup";
import { getApiUrl } from "@/lib/api-url";

interface UseBackupApiOptions {
  poll?: boolean;
}

/**
 * Hook de acesso aos endpoints /admin/backup/*: status (com auto-refresh),
 * lista de cópias, política (GET/PUT), backup manual e restore guiado.
 */
export const useBackupApi = (options?: UseBackupApiOptions) => {
  const poll = options?.poll ?? true;
  const dispatch = useDispatch<AppDispatch>();
  const intervalMs = useSelector(
    (state: RootState) => state.admin.pollingIntervalMs,
  );

  const fetchStatus = useCallback(async (): Promise<void> => {
    try {
      const res = await axios.get(`${getApiUrl()}/admin/backup/status`);
      dispatch(setBackupStatus(res.data));
    } catch (err: any) {
      dispatch(setBackupError(err?.message || "Falha ao buscar status do backup"));
    }
  }, [dispatch]);

  const fetchList = useCallback(async (): Promise<void> => {
    try {
      const res = await axios.get(`${getApiUrl()}/admin/backup/list`);
      dispatch(setBackupList(res.data.archives ?? []));
    } catch (err: any) {
      dispatch(setBackupError(err?.message || "Falha ao listar backups"));
    }
  }, [dispatch]);

  const fetchPolicy = useCallback(async (): Promise<void> => {
    try {
      const res = await axios.get(`${getApiUrl()}/admin/backup/policy`);
      dispatch(setBackupPolicy(res.data));
    } catch (err: any) {
      dispatch(setBackupError(err?.message || "Falha ao buscar política"));
    }
  }, [dispatch]);

  const savePolicy = useCallback(
    async (policy: BackupPolicy): Promise<boolean> => {
      // Guarda client-side: evita PUT com retenção fora do intervalo aceito.
      if (!isValidRetention(policy.retention)) {
        dispatch(setBackupError("Retenção deve ser um inteiro entre 1 e 50"));
        return false;
      }
      dispatch(setBackupLoading());
      try {
        const res = await axios.put(`${getApiUrl()}/admin/backup/policy`, policy);
        dispatch(setBackupPolicy(res.data));
        return true;
      } catch (err: any) {
        dispatch(setBackupError(err?.message || "Falha ao salvar política"));
        return false;
      }
    },
    [dispatch],
  );

  const runBackup = useCallback(async (): Promise<boolean> => {
    dispatch(setBackupLoading());
    try {
      await axios.post(`${getApiUrl()}/admin/backup/run`);
      await fetchStatus();
      await fetchList();
      return true;
    } catch (err: any) {
      dispatch(setBackupError(err?.message || "Falha ao iniciar backup"));
      return false;
    }
  }, [dispatch, fetchStatus, fetchList]);

  const restore = useCallback(
    async (archive: string, confirm: string): Promise<void> => {
      await axios.post(`${getApiUrl()}/admin/backup/restore`, { archive, confirm });
    },
    [],
  );

  usePolling(fetchStatus, intervalMs, poll);

  return { fetchStatus, fetchList, fetchPolicy, savePolicy, runBackup, restore };
};

export default useBackupApi;
