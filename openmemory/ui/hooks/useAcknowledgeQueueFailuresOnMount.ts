import { useEffect, useRef } from "react";
import axios from "axios";
import { useDispatch } from "react-redux";
import { AppDispatch } from "@/store/store";
import {
  bumpQueueUiPrefs,
  setFailedJobIds,
} from "@/store/queuesSlice";
import { acknowledgeFailedJobs } from "@/lib/queue-ui-prefs";
import { getApiUrl } from "@/lib/api-url";
import { PaginatedWriteQueue, PaginatedGovernanceQueue } from "@/types/admin";

/**
 * Marca falhas atuais como vistas ao abrir Filas ou Visão Geral.
 * O badge e os alertas somem até surgir falha nova.
 */
export function useAcknowledgeQueueFailuresOnMount() {
  const dispatch = useDispatch<AppDispatch>();
  const acknowledgedVisit = useRef(false);

  useEffect(() => {
    if (acknowledgedVisit.current) return;
    acknowledgedVisit.current = true;
    let cancelled = false;
    (async () => {
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
        if (cancelled) return;
        const writeIds = writeRes.data.items.map((j) => j.id);
        const govIds = govRes.data.items.map((j) => j.id);
        acknowledgeFailedJobs(writeIds, govIds);
        dispatch(setFailedJobIds({ write: writeIds, governance: govIds }));
        dispatch(bumpQueueUiPrefs());
      } catch {
        // best-effort
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [dispatch]);
}

export default useAcknowledgeQueueFailuresOnMount;
