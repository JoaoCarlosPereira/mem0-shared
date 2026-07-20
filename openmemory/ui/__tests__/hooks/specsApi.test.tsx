import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { renderHook, act } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

import specsReducer from "@/store/specsSlice";
import { useSpecsApi } from "@/hooks/useSpecsApi";
import type { WorkspaceBoard, WorkspaceSummary } from "@/types/specs";

const summary: WorkspaceSummary = {
  id: "w1",
  project_id: "mem0-shared",
  slug: "ws-1",
  name: "WS 1",
  status: "ativo",
  task_counts: { tasks: 1 },
};

const board: WorkspaceBoard = {
  workspace: {
    id: "w1",
    project_id: "mem0-shared",
    slug: "ws-1",
    name: "WS 1",
    status: "ativo",
  },
  documents: [],
  tasks: [],
};

function makeStore() {
  return configureStore({ reducer: { specs: specsReducer } });
}

function wrapperFor(store: ReturnType<typeof makeStore>) {
  return ({ children }: { children: React.ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );
}

beforeEach(() => {
  mockedAxios.get.mockReset();
  mockedAxios.post.mockReset();
  mockedAxios.put.mockReset();
  mockedAxios.patch.mockReset();
});

describe("useSpecsApi", () => {
  it("fetchProjectWorkspaces faz GET no painel e despacha para o slice", async () => {
    mockedAxios.get.mockResolvedValue({ data: [summary] });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchProjectWorkspaces("mem0-shared");
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/projects/mem0-shared/workspaces"),
    );
    expect(store.getState().specs.projectWorkspaces).toEqual([summary]);
  });

  it("fetchWorkspaceBoard faz GET no quadro e despacha para o slice", async () => {
    mockedAxios.get.mockResolvedValue({ data: board });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchWorkspaceBoard("w1");
    });

    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/workspaces/w1"),
    );
    expect(store.getState().specs.currentBoard).toEqual(board);
  });

  it("erro de rede no painel não lança — registra erro no slice", async () => {
    mockedAxios.get.mockRejectedValue(new Error("Network down"));
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    await act(async () => {
      await result.current.fetchProjectWorkspaces("mem0-shared");
    });

    expect(store.getState().specs.error).toBe("Network down");
  });

  it("writeDocument devolve conflict=true no HTTP 409, sem lançar", async () => {
    mockedAxios.put.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: { current_version: 2, current_content: "v2" } },
      },
    });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });

    let res: any;
    await act(async () => {
      res = await result.current.writeDocument("w1", "prd", {
        content: "novo",
        expected_version: 1,
      });
    });

    expect(res.conflict).toBe(true);
    expect(res.current_version).toBe(2);
    expect(res.current_content).toBe("v2");
    expect(mockedAxios.put).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/workspaces/w1/documents/prd"),
      expect.objectContaining({ expected_version: 1 }),
    );
  });

  it("writeDocument devolve conflict=false no sucesso", async () => {
    mockedAxios.put.mockResolvedValue({ data: { document_id: "d1", version: 3 } });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let res: any;
    await act(async () => {
      res = await result.current.writeDocument("w1", "prd", { content: "x" });
    });
    expect(res.conflict).toBe(false);
    expect(res.version).toBe(3);
  });

  it("claimTask devolve claimed=false + assignee atual no 409", async () => {
    mockedAxios.post.mockRejectedValue({
      response: {
        status: 409,
        data: { detail: { current_assignee: "host-a", version: 2 } },
      },
    });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let res: any;
    await act(async () => {
      res = await result.current.claimTask("t1", "host-b");
    });
    expect(res.claimed).toBe(false);
    expect(res.current_assignee).toBe("host-a");
  });

  it("updateTaskStatus devolve conflict=true no 409", async () => {
    mockedAxios.patch.mockRejectedValue({
      response: { status: 409, data: { detail: { current_version: 5, current_status: "em_andamento" } } },
    });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let res: any;
    await act(async () => {
      res = await result.current.updateTaskStatus("t1", {
        expected_version: 1,
        new_status: "concluido",
      });
    });
    expect(res.conflict).toBe(true);
    expect(res.current_status).toBe("em_andamento");
  });

  it("searchSpecs passa q e project_id como query params", async () => {
    mockedAxios.get.mockResolvedValue({ data: [] });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.searchSpecs("como fazer X", "mem0-shared");
    });
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/search"),
      expect.objectContaining({
        params: expect.objectContaining({ q: "como fazer X", project_id: "mem0-shared" }),
      }),
    );
  });

  it("createWorkspace faz POST /workspaces e devolve o workspace", async () => {
    mockedAxios.post.mockResolvedValue({ data: board.workspace });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let res: any;
    await act(async () => {
      res = await result.current.createWorkspace({
        project_id: "mem0-shared",
        slug: "ws-1",
        name: "WS 1",
      });
    });
    expect(res.id).toBe("w1");
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/workspaces"),
      expect.objectContaining({ slug: "ws-1" }),
    );
  });

  it("fetchDocumentVersions faz GET no histórico de versões", async () => {
    mockedAxios.get.mockResolvedValue({ data: [] });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.fetchDocumentVersions("w1", "techspec");
    });
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/workspaces/w1/documents/techspec/versions"),
    );
  });

  it("createTask faz POST /tasks", async () => {
    mockedAxios.post.mockResolvedValue({ data: { id: "t1" } });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.createTask({ workspace_id: "w1", title: "Card" });
    });
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/tasks"),
      expect.objectContaining({ title: "Card" }),
    );
  });

  it("releaseTask faz POST /tasks/{id}/release", async () => {
    mockedAxios.post.mockResolvedValue({ data: { id: "t1", status: "tasks" } });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.releaseTask("t1", { actor: "admin" });
    });
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/tasks/t1/release"),
      expect.objectContaining({ actor: "admin" }),
    );
  });

  it("claimTask devolve claimed=true no sucesso", async () => {
    mockedAxios.post.mockResolvedValue({ data: { id: "t1", version: 2, status: "em_andamento" } });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let res: any;
    await act(async () => {
      res = await result.current.claimTask("t1", "host-a");
    });
    expect(res.claimed).toBe(true);
    expect(res.version).toBe(2);
  });

  it("updateTaskStatus devolve conflict=false no sucesso", async () => {
    mockedAxios.patch.mockResolvedValue({ data: { id: "t1", status: "revisao_codigo" } });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    let res: any;
    await act(async () => {
      res = await result.current.updateTaskStatus("t1", { expected_version: 1, new_status: "revisao_codigo" });
    });
    expect(res.conflict).toBe(false);
    expect(res.task.status).toBe("revisao_codigo");
  });

  it("createComment faz POST /comments", async () => {
    mockedAxios.post.mockResolvedValue({ data: { id: "c1" } });
    const store = makeStore();
    const { result } = renderHook(() => useSpecsApi({ poll: false }), {
      wrapper: wrapperFor(store),
    });
    await act(async () => {
      await result.current.createComment({
        target_type: "task",
        target_id: "t1",
        body: "oi",
      });
    });
    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/comments"),
      expect.objectContaining({ body: "oi" }),
    );
  });

  it("polling do painel dispara fetch ao montar quando projectId informado", () => {
    jest.useFakeTimers();
    mockedAxios.get.mockResolvedValue({ data: [summary] });
    const store = makeStore();
    renderHook(() => useSpecsApi({ projectId: "mem0-shared" }), {
      wrapper: wrapperFor(store),
    });
    expect(mockedAxios.get).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/specs/projects/mem0-shared/workspaces"),
    );
    jest.useRealTimers();
  });
});
