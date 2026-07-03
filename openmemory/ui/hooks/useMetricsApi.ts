import { useCallback } from "react";
import axios from "axios";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import {
  setDetailsData,
  setMetricsError,
  setMetricsLoading,
  setSummaryData,
} from "@/store/metricsSlice";
import {
  MetricsFilters,
  SortBy,
  SortOrder,
  TokenDetailsResponse,
  TokenSummaryResponse,
} from "@/types/metrics";
import { getApiUrl } from "@/lib/api-url";

export interface DetailsOptions {
  page?: number;
  pageSize?: number;
  sortBy?: SortBy;
  sortOrder?: SortOrder;
}

function filterParams(filters: MetricsFilters) {
  return {
    start: filters.start,
    end: filters.end || undefined,
    operation_type: filters.operation_type?.length
      ? filters.operation_type
      : undefined,
    project: filters.project || undefined,
    agent: filters.agent || undefined,
    user_id: filters.user_id || undefined,
    model: filters.model || undefined,
  };
}

/**
 * Hook de acesso aos endpoints de métricas de tokens
 * (`/api/v1/metrics/tokens/*`). Despacha dados para o `metricsSlice`.
 */
export const useMetricsApi = () => {
  const dispatch = useDispatch<AppDispatch>();
  const summary = useSelector((state: RootState) => state.metrics.summary);
  const details = useSelector((state: RootState) => state.metrics.details);
  const loading = useSelector((state: RootState) => state.metrics.loading);
  const error = useSelector((state: RootState) => state.metrics.error);

  const fetchSummary = useCallback(
    async (filters: MetricsFilters): Promise<TokenSummaryResponse | null> => {
      dispatch(setMetricsLoading());
      try {
        const res = await axios.get<TokenSummaryResponse>(
          `${getApiUrl()}/api/v1/metrics/tokens/summary`,
          {
            params: {
              ...filterParams(filters),
              granularity: filters.granularity,
            },
            paramsSerializer: { indexes: null },
          },
        );
        dispatch(setSummaryData(res.data));
        return res.data;
      } catch (err: any) {
        dispatch(
          setMetricsError(err?.message || "Falha ao buscar métricas de tokens"),
        );
        return null;
      }
    },
    [dispatch],
  );

  const fetchDetails = useCallback(
    async (
      filters: MetricsFilters,
      options?: DetailsOptions,
    ): Promise<TokenDetailsResponse | null> => {
      dispatch(setMetricsLoading());
      try {
        const res = await axios.get<TokenDetailsResponse>(
          `${getApiUrl()}/api/v1/metrics/tokens/details`,
          {
            params: {
              ...filterParams(filters),
              page: options?.page ?? 1,
              page_size: options?.pageSize ?? 50,
              sort_by: options?.sortBy ?? "created_at",
              sort_order: options?.sortOrder ?? "desc",
            },
            paramsSerializer: { indexes: null },
          },
        );
        dispatch(setDetailsData(res.data));
        return res.data;
      } catch (err: any) {
        dispatch(
          setMetricsError(err?.message || "Falha ao buscar detalhes de tokens"),
        );
        return null;
      }
    },
    [dispatch],
  );

  const exportCsv = useCallback(
    async (filters: MetricsFilters): Promise<boolean> => {
      try {
        const res = await axios.get(
          `${getApiUrl()}/api/v1/metrics/tokens/export`,
          {
            params: filterParams(filters),
            paramsSerializer: { indexes: null },
            responseType: "blob",
          },
        );
        const url = window.URL.createObjectURL(new Blob([res.data]));
        const link = document.createElement("a");
        link.href = url;
        link.download = `token-usage-${filters.start.slice(0, 10)}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        return true;
      } catch (err: any) {
        dispatch(
          setMetricsError(err?.message || "Falha ao exportar CSV de tokens"),
        );
        return false;
      }
    },
    [dispatch],
  );

  return {
    summary,
    details,
    loading,
    error,
    fetchSummary,
    fetchDetails,
    exportCsv,
  };
};
