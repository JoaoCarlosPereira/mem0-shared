import { useCallback } from "react";
import axios from "axios";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import {
  setAdminOverview,
  setAdminLoading,
  setAdminError,
} from "@/store/adminSlice";
import { usePolling } from "@/hooks/usePolling";
import {
  PaginatedWriteAudit,
  ProjectMemoriesResponse,
  ProjectSizesResponse,
  WriteAuditFilter,
} from "@/types/admin";
import { getApiUrl } from "@/lib/api-url";


interface UseAdminApiOptions {
  // Quando false, desativa o auto-refresh do overview (ex.: página de audit).
  poll?: boolean;
}

/**
 * Hook de acesso aos endpoints admin globais: overview (com auto-refresh) e
 * write-audit (sob demanda). Despacha o overview para o `adminSlice`.
 */
export const useAdminApi = (options?: UseAdminApiOptions) => {
  const poll = options?.poll ?? true;
  const dispatch = useDispatch<AppDispatch>();
  const intervalMs = useSelector(
    (state: RootState) => state.admin.pollingIntervalMs,
  );

  const fetchAdminOverview = useCallback(async (): Promise<void> => {
    dispatch(setAdminLoading());
    try {
      const res = await axios.get(`${getApiUrl()}/admin/overview`);
      dispatch(setAdminOverview(res.data));
    } catch (err: any) {
      dispatch(setAdminError(err?.message || "Falha ao buscar visão geral"));
    }
  }, [dispatch]);

  const fetchWriteAudit = useCallback(
    async (filters: WriteAuditFilter): Promise<PaginatedWriteAudit> => {
      const res = await axios.get<PaginatedWriteAudit>(
        `${getApiUrl()}/admin/write-audit`,
        {
          params: {
            project: filters.project || undefined,
            hostname: filters.hostname || undefined,
            from_date: filters.from_date || undefined,
            to_date: filters.to_date || undefined,
            page: filters.page,
          },
        },
      );
      return res.data;
    },
    [],
  );

  const fetchProjectSizes =
    useCallback(async (): Promise<ProjectSizesResponse> => {
      const res = await axios.get<ProjectSizesResponse>(
        `${getApiUrl()}/admin/projects/sizes`,
      );
      return res.data;
    }, []);

  // Lê as memórias de um projeto direto do store vetorial (Qdrant) — fonte do
  // caminho MCP compartilhado, indexada por projeto (não a tabela SQL).
  const fetchProjectMemories = useCallback(
    async (project: string, search?: string): Promise<ProjectMemoriesResponse> => {
      const res = await axios.get<ProjectMemoriesResponse>(
        `${getApiUrl()}/admin/projects/${encodeURIComponent(project)}/memories`,
        { params: { search: search || undefined } },
      );
      return res.data;
    },
    [],
  );

  usePolling(fetchAdminOverview, intervalMs, poll);

  return {
    fetchAdminOverview,
    fetchWriteAudit,
    fetchProjectSizes,
    fetchProjectMemories,
  };
};

export default useAdminApi;
