import { useCallback } from "react";
import axios from "axios";
import { getApiUrl } from "@/lib/api-url";

export interface Group {
  id: string;
  name: string;
  member_count: number;
}

export interface GroupMember {
  id: string;
  user_id: string;
  name?: string | null;
  display_name?: string | null;
  avatar_url?: string | null;
}

/**
 * Hook de acesso aos endpoints de gestão de grupos (`/admin/groups`) — task_06/08.
 * Segue o padrão de `useAdminApi`: axios + `getApiUrl()` (proxy `/api-proxy`).
 */
export const useGroupsApi = () => {
  const fetchGroups = useCallback(async (): Promise<Group[]> => {
    const res = await axios.get<{ groups: Group[] }>(`${getApiUrl()}/admin/groups`);
    return res.data.groups;
  }, []);

  const createGroup = useCallback(async (name: string): Promise<Group> => {
    const res = await axios.post<Group>(`${getApiUrl()}/admin/groups`, { name });
    return res.data;
  }, []);

  const updateGroup = useCallback(
    async (groupId: string, name: string): Promise<Group> => {
      const res = await axios.put<Group>(
        `${getApiUrl()}/admin/groups/${groupId}`,
        { name },
      );
      return res.data;
    },
    [],
  );

  const deleteGroup = useCallback(async (groupId: string): Promise<void> => {
    await axios.delete(`${getApiUrl()}/admin/groups/${groupId}`);
  }, []);

  const fetchMembers = useCallback(
    async (groupId: string): Promise<GroupMember[]> => {
      const res = await axios.get<{ members: GroupMember[] }>(
        `${getApiUrl()}/admin/groups/${groupId}/members`,
      );
      return res.data.members;
    },
    [],
  );

  const addMember = useCallback(
    async (groupId: string, userId: string): Promise<GroupMember> => {
      const res = await axios.post<GroupMember>(
        `${getApiUrl()}/admin/groups/${groupId}/members`,
        { user_id: userId },
      );
      return res.data;
    },
    [],
  );

  const removeMember = useCallback(
    async (groupId: string, userId: string): Promise<void> => {
      await axios.delete(
        `${getApiUrl()}/admin/groups/${groupId}/members/${encodeURIComponent(userId)}`,
      );
    },
    [],
  );

  return {
    fetchGroups,
    createGroup,
    updateGroup,
    deleteGroup,
    fetchMembers,
    addMember,
    removeMember,
  };
};

export default useGroupsApi;
