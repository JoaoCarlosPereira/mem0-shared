import { renderHook, act } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

import { useGroupsApi } from "@/hooks/useGroupsApi";

beforeEach(() => {
  mockedAxios.get.mockReset();
  mockedAxios.post.mockReset();
  mockedAxios.put.mockReset();
  mockedAxios.delete.mockReset();
});

describe("useGroupsApi (task_08)", () => {
  it("fetchGroups faz GET /admin/groups e retorna a lista", async () => {
    const groups = [{ id: "g1", name: "Equipe A", member_count: 2 }];
    mockedAxios.get.mockResolvedValue({ data: { groups } });
    const { result } = renderHook(() => useGroupsApi());

    let out: any;
    await act(async () => {
      out = await result.current.fetchGroups();
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/groups"),
    );
    expect(out).toEqual(groups);
  });

  it("fetchMemberCandidates faz GET /admin/groups/member-candidates", async () => {
    const candidates = [
      { id: "c1", user_id: "S0136", display_name: "Mauricio", group_name: "Default" },
    ];
    mockedAxios.get.mockResolvedValue({ data: { candidates } });
    const { result } = renderHook(() => useGroupsApi());

    let out: any;
    await act(async () => {
      out = await result.current.fetchMemberCandidates();
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/admin/groups/member-candidates"),
    );
    expect(out).toEqual(candidates);
  });

  it("createGroup faz POST /admin/groups com o nome", async () => {
    mockedAxios.post.mockResolvedValue({
      data: { id: "g2", name: "Nova", member_count: 0 },
    });
    const { result } = renderHook(() => useGroupsApi());

    await act(async () => {
      await result.current.createGroup("Nova");
    });

    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/admin/groups"),
      { name: "Nova" },
    );
  });

  it("addMember faz POST .../members com user_id", async () => {
    mockedAxios.post.mockResolvedValue({ data: { id: "u1", user_id: "host-x" } });
    const { result } = renderHook(() => useGroupsApi());

    await act(async () => {
      await result.current.addMember("g1", "host-x");
    });

    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/admin/groups/g1/members"),
      { user_id: "host-x" },
    );
  });

  it("removeMember faz DELETE .../members/{user_id} URL-encoded", async () => {
    mockedAxios.delete.mockResolvedValue({ data: {} });
    const { result } = renderHook(() => useGroupsApi());

    await act(async () => {
      await result.current.removeMember("g1", "host com espaço");
    });

    expect(mockedAxios.delete).toHaveBeenCalledWith(
      expect.stringContaining("/admin/groups/g1/members/host%20com%20espa%C3%A7o"),
    );
  });

  it("deleteGroup faz DELETE /admin/groups/{id}", async () => {
    mockedAxios.delete.mockResolvedValue({ data: {} });
    const { result } = renderHook(() => useGroupsApi());

    await act(async () => {
      await result.current.deleteGroup("g9");
    });

    expect(mockedAxios.delete).toHaveBeenCalledWith(
      expect.stringContaining("/admin/groups/g9"),
    );
  });
});
