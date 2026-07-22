import specsReducer, {
  setAllWorkspaces,
  setProjectWorkspaces,
  setCurrentBoard,
  setSpecsLoading,
  setSpecsError,
  setSpecsPollingInterval,
} from "@/store/specsSlice";
import type { WorkspaceBoard, WorkspaceSummary } from "@/types/specs";

const summary: WorkspaceSummary = {
  id: "w1",
  project_id: "mem0-shared",
  slug: "ws-1",
  name: "WS 1",
  status: "ativo",
  task_counts: { tasks: 2, em_andamento: 1 },
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

describe("specsSlice", () => {
  it("estado inicial: sem dados, pollingIntervalMs=15000", () => {
    const state = specsReducer(undefined, { type: "@@INIT" });
    expect(state.projectWorkspaces).toBeNull();
    expect(state.currentBoard).toBeNull();
    expect(state.pollingIntervalMs).toBe(15000);
    expect(state.loading).toBe(false);
  });

  it("setSpecsLoading liga loading e limpa erro", () => {
    const state = specsReducer(
      { ...specsReducer(undefined, { type: "@@INIT" }), error: "x" },
      setSpecsLoading(),
    );
    expect(state.loading).toBe(true);
    expect(state.error).toBeNull();
  });

  it("setAllWorkspaces preenche o índice global e desliga loading", () => {
    const state = specsReducer(undefined, setAllWorkspaces([summary]));
    expect(state.allWorkspaces).toEqual([summary]);
    expect(state.loading).toBe(false);
  });

  it("setProjectWorkspaces preenche o painel e desliga loading", () => {
    const state = specsReducer(undefined, setProjectWorkspaces([summary]));
    expect(state.projectWorkspaces).toEqual([summary]);
    expect(state.loading).toBe(false);
    expect(state.error).toBeNull();
  });

  it("setCurrentBoard preenche o quadro", () => {
    const state = specsReducer(undefined, setCurrentBoard(board));
    expect(state.currentBoard).toEqual(board);
  });

  it("setSpecsError registra erro e desliga loading", () => {
    const state = specsReducer(undefined, setSpecsError("boom"));
    expect(state.error).toBe("boom");
    expect(state.loading).toBe(false);
  });

  it("setSpecsPollingInterval mantém a faixa 10000–60000", () => {
    expect(specsReducer(undefined, setSpecsPollingInterval(30000)).pollingIntervalMs).toBe(30000);
    expect(specsReducer(undefined, setSpecsPollingInterval(5000)).pollingIntervalMs).toBe(10000);
    expect(specsReducer(undefined, setSpecsPollingInterval(120000)).pollingIntervalMs).toBe(60000);
  });
});
