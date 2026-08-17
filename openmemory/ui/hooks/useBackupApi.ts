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
  setRestoring,
  setRestoreMessage,
} from "@/store/backupSlice";
import { usePolling } from "@/hooks/usePolling";
import { isValidRetention } from "@/lib/backup";
import { getApiUrl } from "@/lib/api-url";

interface UseBackupApiOptions {
  poll?: boolean;
}

function backupApiError(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (err.response?.status === 401) {
      return (
        "Não autorizado (401): mutações de backup exigem sessão Google ou " +
        "ADMIN_TOKEN no proxy da UI."
      );
    }
    if (err.message) return err.message;
  }
  if (err instanceof Error && err.message) return err.message;
  return fallback;
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
    } catch (err: unknown) {
      dispatch(setBackupError(backupApiError(err, "Falha ao buscar status do backup")));
    }
  }, [dispatch]);

  const fetchList = useCallback(async (): Promise<void> => {
    try {
      const res = await axios.get(`${getApiUrl()}/admin/backup/list`);
      dispatch(setBackupList(res.data.archives ?? []));
    } catch (err: unknown) {
      dispatch(setBackupError(backupApiError(err, "Falha ao listar backups")));
    }
  }, [dispatch]);

  const fetchPolicy = useCallback(async (): Promise<void> => {
    try {
      const res = await axios.get(`${getApiUrl()}/admin/backup/policy`);
      dispatch(setBackupPolicy(res.data));
    } catch (err: unknown) {
      dispatch(setBackupError(backupApiError(err, "Falha ao buscar política")));
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
      } catch (err: unknown) {
        dispatch(setBackupError(backupApiError(err, "Falha ao salvar política")));
        return false;
      }
    },
    [dispatch],
  );

  const runBackup = useCallback(async (): Promise<boolean> => {
    dispatch(setBackupLoading());
    try {
      const before = (
        await axios.get(`${getApiUrl()}/admin/backup/status`)
      ).data;
      const beforeCount = Number(before?.archives ?? 0);
      await axios.post(`${getApiUrl()}/admin/backup/run`);
      // Backup roda em background (snapshot Qdrant ~20–90s). Poll até aparecer
      // nova cópia ou last_error — senão a UI parece “não fazer nada”.
      const deadline = Date.now() + 180_000;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 3000));
        const st = (await axios.get(`${getApiUrl()}/admin/backup/status`)).data;
        dispatch(setBackupStatus(st));
        if (st?.last_error) {
          dispatch(setBackupError(String(st.last_error)));
          await fetchList();
          return false;
        }
        if (Number(st?.archives ?? 0) > beforeCount) {
          await fetchList();
          return true;
        }
      }
      await fetchStatus();
      await fetchList();
      dispatch(
        setBackupError(
          "Backup aceito, mas ainda não concluiu em 3 min. Atualize o status em breve.",
        ),
      );
      return false;
    } catch (err: unknown) {
      dispatch(setBackupError(backupApiError(err, "Falha ao iniciar backup")));
      return false;
    }
  }, [dispatch, fetchStatus, fetchList]);

  const restore = useCallback(
    async (archive: string, confirm: string): Promise<boolean> => {
      dispatch(setRestoring(true));
      try {
        const before = (
          await axios.get(`${getApiUrl()}/admin/backup/status`)
        ).data;
        const beforeCount = Number(before?.archives ?? 0);
        await axios.post(`${getApiUrl()}/admin/backup/restore`, {
          archive,
          confirm,
        });
        // Restore roda em background (202). A conclusão é assinalada pela
        // criação do snapshot de segurança pre-restore-*.zip (aumenta a
        // contagem de cópias) — até lá a UI mostra "em andamento".
        const deadline = Date.now() + 180_000;
        while (Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, 3000));
          const st = (await axios.get(`${getApiUrl()}/admin/backup/status`)).data;
          dispatch(setBackupStatus(st));
          if (st?.last_error) {
            dispatch(setBackupError(String(st.last_error)));
            dispatch(setRestoring(false));
            await fetchList();
            return false;
          }
          if (Number(st?.archives ?? 0) > beforeCount) {
            await fetchList();
            dispatch(setRestoreMessage(`Restore de ${archive} concluído.`));
            return true;
          }
        }
        await fetchStatus();
        await fetchList();
        dispatch(
          setRestoreMessage(
            "Restore aceito, mas ainda não concluiu em 3 min. Atualize o status em breve.",
          ),
        );
        return false;
      } catch (err: unknown) {
        dispatch(setBackupError(backupApiError(err, "Falha ao restaurar backup")));
        dispatch(setRestoring(false));
        return false;
      }
    },
    [dispatch, fetchStatus, fetchList],
  );

  usePolling(fetchStatus, intervalMs, poll);

  return { fetchStatus, fetchList, fetchPolicy, savePolicy, runBackup, restore };
};

export default useBackupApi;
