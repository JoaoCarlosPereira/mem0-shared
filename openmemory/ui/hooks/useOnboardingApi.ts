import { useCallback } from "react";
import axios from "axios";
import { getApiUrl } from "@/lib/api-url";

export interface OnboardingResult {
  linked: boolean;
  hostname: string;
  group: string;
  memories_count: number;
  legacy_user_linked: boolean;
}

export interface MachineSuggestions {
  detected_hostname: string | null;
  unlinked_hostnames: string[];
  suggested_group?: string | null;
}

/**
 * Hook do onboarding de primeiro login (feature auth Google, task_08).
 * Padrão de `useGroupsApi`: axios + `getApiUrl()` (o Bearer da sessão é
 * anexado pelo interceptor global de `lib/api-client`).
 */
export const useOnboardingApi = () => {
  const submitOnboarding = useCallback(
    async (hostname: string, groupName: string | null): Promise<OnboardingResult> => {
      const res = await axios.post<OnboardingResult>(
        `${getApiUrl()}/api/v1/auth/onboarding`,
        { hostname, group_name: groupName },
      );
      return res.data;
    },
    [],
  );

  const fetchMachineSuggestions = useCallback(async (): Promise<MachineSuggestions> => {
    const res = await axios.get<MachineSuggestions>(
      `${getApiUrl()}/api/v1/auth/machine-suggestions`,
    );
    return res.data;
  }, []);

  return { submitOnboarding, fetchMachineSuggestions };
};

export default useOnboardingApi;
