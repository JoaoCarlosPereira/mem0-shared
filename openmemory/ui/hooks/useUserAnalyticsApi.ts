import { useCallback } from "react";
import axios from "axios";
import { getApiUrl } from "@/lib/api-url";
import type {
  AnalyticsOverview,
  GroupAnalytics,
  GroupAnalyticsDetail,
  UserAnalyticsDetail,
} from "@/types/admin";

export const useUserAnalyticsApi = () => {
  const fetchOverview = useCallback(async (): Promise<AnalyticsOverview> => {
    const res = await axios.get<AnalyticsOverview>(
      `${getApiUrl()}/admin/analytics/overview`,
    );
    return res.data;
  }, []);

  const fetchGroupsAnalytics = useCallback(async (): Promise<GroupAnalytics[]> => {
    const res = await axios.get<{ groups: GroupAnalytics[] }>(
      `${getApiUrl()}/admin/analytics/groups`,
    );
    return res.data.groups;
  }, []);

  const fetchGroupAnalytics = useCallback(
    async (groupId: string): Promise<GroupAnalyticsDetail> => {
      const res = await axios.get<GroupAnalyticsDetail>(
        `${getApiUrl()}/admin/analytics/groups/${groupId}`,
      );
      return res.data;
    },
    [],
  );

  const fetchUserAnalytics = useCallback(
    async (hostname: string): Promise<UserAnalyticsDetail> => {
      const res = await axios.get<UserAnalyticsDetail>(
        `${getApiUrl()}/admin/analytics/users/${encodeURIComponent(hostname)}`,
      );
      return res.data;
    },
    [],
  );

  const deleteLegacyUser = useCallback(async (hostname: string): Promise<void> => {
    await axios.delete(
      `${getApiUrl()}/admin/analytics/users/${encodeURIComponent(hostname)}`,
      { data: { confirm: hostname } },
    );
  }, []);

  return {
    fetchOverview,
    fetchGroupsAnalytics,
    fetchGroupAnalytics,
    fetchUserAnalytics,
    deleteLegacyUser,
  };
};

export default useUserAnalyticsApi;
