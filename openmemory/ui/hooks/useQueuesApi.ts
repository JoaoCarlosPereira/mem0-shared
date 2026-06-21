import { useCallback } from "react";
import axios from "axios";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import {
  setWriteQueue,
  setGovernanceQueue,
  setQueuesLoading,
  setQueuesError,
} from "@/store/queuesSlice";
import { usePolling } from "@/hooks/usePolling";
import { PaginatedWriteQueue, PaginatedGovernanceQueue } from "@/types/admin";

const URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8765";

interface UseQueuesApiOptions {
  poll?: boolean;
}

/**
 * Hook de acesso às filas de processamento: write-queue e governance jobs.
 * Lê os filtros ativos do `queuesSlice`, despacha os resultados de volta e
 * mantém o auto-refresh via `usePolling`.
 */
export const useQueuesApi = (options?: UseQueuesApiOptions) => {
  const poll = options?.poll ?? true;
  const dispatch = useDispatch<AppDispatch>();
  const writeFilter = useSelector(
    (state: RootState) => state.queues.writeQueueFilter,
  );
  const govFilter = useSelector(
    (state: RootState) => state.queues.governanceFilter,
  );
  const intervalMs = useSelector(
    (state: RootState) => state.admin.pollingIntervalMs,
  );

  const fetchWriteQueue = useCallback(async (): Promise<void> => {
    dispatch(setQueuesLoading());
    try {
      const res = await axios.get<PaginatedWriteQueue>(
        `${URL}/admin/write-queue`,
        {
          params: {
            status: writeFilter.status || undefined,
            project: writeFilter.project || undefined,
            page: writeFilter.page,
          },
        },
      );
      dispatch(setWriteQueue(res.data));
    } catch (err: any) {
      dispatch(setQueuesError(err?.message || "Failed to fetch write queue"));
    }
  }, [dispatch, writeFilter.status, writeFilter.project, writeFilter.page]);

  const fetchGovernanceJobs = useCallback(async (): Promise<void> => {
    dispatch(setQueuesLoading());
    try {
      const res = await axios.get<PaginatedGovernanceQueue>(
        `${URL}/admin/governance/jobs`,
        {
          params: {
            status: govFilter.status || undefined,
            job_type: govFilter.job_type || undefined,
            project: govFilter.project || undefined,
            page: govFilter.page,
          },
        },
      );
      dispatch(setGovernanceQueue(res.data));
    } catch (err: any) {
      dispatch(
        setQueuesError(err?.message || "Failed to fetch governance jobs"),
      );
    }
  }, [
    dispatch,
    govFilter.status,
    govFilter.job_type,
    govFilter.project,
    govFilter.page,
  ]);

  const refreshAll = useCallback(async (): Promise<void> => {
    await Promise.allSettled([fetchWriteQueue(), fetchGovernanceJobs()]);
  }, [fetchWriteQueue, fetchGovernanceJobs]);

  usePolling(refreshAll, intervalMs, poll);

  return { fetchWriteQueue, fetchGovernanceJobs, refreshAll };
};

export default useQueuesApi;
