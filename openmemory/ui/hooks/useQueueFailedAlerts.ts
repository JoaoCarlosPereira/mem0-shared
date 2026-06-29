import { useCallback } from "react";
import axios from "axios";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import { setFailedJobIds, bumpQueueUiPrefs } from "@/store/queuesSlice";
import { usePolling } from "@/hooks/usePolling";
import { PaginatedWriteQueue, PaginatedGovernanceQueue } from "@/types/admin";
import { getApiUrl } from "@/lib/api-url";
import { pruneAcknowledgedFailed } from "@/lib/queue-ui-prefs";

/**
 * Mantém IDs de jobs failed atualizados para o badge da sidebar (Filas).
 * Roda em qualquer página admin que monte a sidebar.
 */
export function useQueueFailedAlerts() {
  const dispatch = useDispatch<AppDispatch>();
  const intervalMs = useSelector(
    (state: RootState) => state.admin.pollingIntervalMs,
  );

  const fetchFailedIds = useCallback(async (): Promise<void> => {
    try {
      const [writeRes, govRes] = await Promise.all([
        axios.get<PaginatedWriteQueue>(`${getApiUrl()}/admin/write-queue`, {
          params: { status: "failed", page: 1, page_size: 100 },
        }),
        axios.get<PaginatedGovernanceQueue>(
          `${getApiUrl()}/admin/governance/jobs`,
          { params: { status: "failed", page: 1, page_size: 100 } },
        ),
      ]);
      const writeIds = writeRes.data.items.map((j) => j.id);
      const govIds = govRes.data.items.map((j) => j.id);
      pruneAcknowledgedFailed(writeIds, govIds);
      dispatch(setFailedJobIds({ write: writeIds, governance: govIds }));
      dispatch(bumpQueueUiPrefs());
    } catch {
      // Badge é best-effort; não bloqueia a UI.
    }
  }, [dispatch]);

  usePolling(fetchFailedIds, intervalMs, true);

  return { fetchFailedIds };
}

export default useQueueFailedAlerts;
