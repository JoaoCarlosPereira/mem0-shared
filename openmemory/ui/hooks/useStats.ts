import { useState, useCallback } from "react";
import axios from "axios";
import { useDispatch, useSelector } from "react-redux";
import { AppDispatch, RootState } from "@/store/store";
import { setApps, setTotalApps, setTotalMemories } from "@/store/profileSlice";
import { getApiUrl } from "@/lib/api-url";
import { getApiAccessToken } from "@/lib/api-client";

interface APIStatsResponse {
  total_memories: number;
  total_apps: number;
  apps: unknown[];
}

interface UseStatsReturn {
  fetchStats: () => Promise<void>;
  isLoading: boolean;
  error: string | null;
}

export const useStats = (): UseStatsReturn => {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const dispatch = useDispatch<AppDispatch>();
  const user_id = useSelector((state: RootState) => state.profile.userId);

  const fetchStats = useCallback(async () => {
    if (!getApiAccessToken()) {
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      const response = await axios.get<APIStatsResponse>(
        `${getApiUrl()}/api/v1/stats/?user_id=${user_id}`,
      );
      dispatch(setTotalMemories(response.data.total_memories));
      dispatch(setTotalApps(response.data.total_apps));
      dispatch(setApps(response.data.apps));
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Falha ao buscar estatísticas";
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [dispatch, user_id]);

  return { fetchStats, isLoading, error };
};
