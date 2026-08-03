import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

jest.mock("next/navigation", () => ({
  useParams: () => ({ project: "mem0-shared", workspace: "ws-1" }),
}));

jest.mock(
  "@dnd-kit/core",
  () => ({
    DndContext: ({ children }: any) => <div data-testid="dnd">{children}</div>,
    DragOverlay: ({ children }: any) => <div data-testid="dnd-overlay">{children}</div>,
    DragEndEvent: {},
    DragOverEvent: {},
    DragStartEvent: {},
    PointerSensor: jest.fn(),
    TouchSensor: jest.fn(),
    closestCorners: jest.fn(),
    pointerWithin: jest.fn(() => []),
    rectIntersection: jest.fn(() => []),
    useDraggable: () => ({
      attributes: {},
      listeners: {},
      setNodeRef: jest.fn(),
      isDragging: false,
    }),
    useDroppable: () => ({ setNodeRef: jest.fn(), isOver: false }),
    useSensor: jest.fn(),
    useSensors: jest.fn(() => []),
  }),
  { virtual: true },
);

const updateTaskStatus = jest.fn();
const updateTask = jest.fn();
const deleteTask = jest.fn();
const deleteDocument = jest.fn();
const writeDocument = jest.fn();
const claimTask = jest.fn();
const releaseTask = jest.fn();
const createTask = jest.fn();
const fetchWorkspaceBoard = jest.fn();
jest.mock("@/hooks/useSpecsApi", () => ({
  useSpecsApi: jest.fn(() => ({
    updateTaskStatus,
    updateTask,
    deleteTask,
    deleteDocument,
    writeDocument,
    claimTask,
    releaseTask,
    createTask,
    fetchWorkspaceBoard,
    listLabels: jest.fn().mockResolvedValue([]),
    createLabel: jest.fn(),
    attachLabel: jest.fn(),
    detachLabel: jest.fn(),
    listChecklists: jest.fn().mockResolvedValue([]),
    createChecklist: jest.fn(),
    createChecklistItem: jest.fn(),
    patchChecklistItem: jest.fn(),
    uploadAttachment: jest.fn(),
    deleteAttachment: jest.fn(),
    attachmentDownloadUrl: jest.fn((id: string) => `/att/${id}`),
  })),
}));

import specsReducer, { setCurrentBoard } from "@/store/specsSlice";
import SpecsBoardPage from "@/app/docs/[project]/[workspace]/page";
import type { WorkspaceBoard } from "@/types/specs";

const board: WorkspaceBoard = {
  workspace: {
    id: "ws-1",
    project_id: "mem0-shared",
    slug: "ws-1",
    name: "Feature A",
    status: "ativo",
  },
  documents: [
    {
      id: "d1",
      workspace_id: "ws-1",
      document_type: "prd",
      current_version: 2,
      current_content: "# Hello PRD\n\nVer [ADR-001: Teste](adrs/adr-001.md).",
    },
    {
      id: "d-adrs",
      workspace_id: "ws-1",
      document_type: "adrs",
      current_version: 1,
      current_content: "# ADRs\n\n### ADR-001: Teste\n\n**Decisão**\nok",
    },
  ],
  tasks: [
    {
      id: "t1",
      workspace_id: "ws-1",
      title: "Card em andamento",
      status: "em_andamento",
      is_blocked: false,
      assignee: "host-a",
      assignee_display_name: "Ana Silva",
      assignee_avatar_url: "https://example.com/ana.png",
      version: 4,
    },
    {
      id: "t2",
      workspace_id: "ws-1",
      title: "Card backlog",
      status: "tasks",
      is_blocked: true,
      block_reason: "dep externa",
      version: 1,
    },
  ],
};

function makeStore() {
  return configureStore({ reducer: { specs: specsReducer } });
}

function renderWith(store: ReturnType<typeof makeStore>) {
  return render(
    <Provider store={store}>
      <SpecsBoardPage />
    </Provider>,
  );
}

beforeEach(() => {
  updateTaskStatus.mockReset();
  updateTask.mockReset();
  deleteTask.mockReset();
  deleteDocument.mockReset();
  writeDocument.mockReset();
  claimTask.mockReset();
  releaseTask.mockReset();
  createTask.mockReset();
  fetchWorkspaceBoard.mockReset();
});

describe("SpecsBoardPage", () => {
  it("renderiza as colunas fixas do sistema", () => {
    renderWith(makeStore());
    [
      "SDD",
      "Tasks",
      "Em andamento",
      "Revisão de código",
      "Fase de teste",
      "Concluído",
    ].forEach((label) => expect(screen.getByText(label)).toBeInTheDocument());
  });

  it("documento aparece na coluna SDD com a versão atual", () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const sdd = screen.getByTestId("column-SDD");
    expect(within(sdd).getByText("prd")).toBeInTheDocument();
    expect(within(sdd).getByText("versão v2")).toBeInTheDocument();
    expect(within(sdd).getByText("adrs")).toBeInTheDocument();
    expect(within(sdd).getByTestId("doc-card-adrs")).toBeInTheDocument();
  });

  it("link adrs/*.md no PRD abre o documento adrs", async () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    await userEvent.click(screen.getByTestId("doc-card-prd"));
    const link = await screen.findByRole("link", { name: /ADR-001/i });
    await userEvent.click(link);
    expect(await screen.findByText(/ADRs do workspace/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: /ADR-001/ })).toBeInTheDocument();
  });

  it("card de task exibe o responsável quando presente", () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const card = screen.getByTestId("task-card-t1");
    expect(within(card).getByText("Ana Silva")).toBeInTheDocument();
    const avatar = within(card).getByTestId("task-assignee-t1").querySelector("img");
    expect(avatar).toHaveAttribute("src", "https://example.com/ana.png");
  });

  it("card bloqueado exibe o badge de bloqueio", () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const card = screen.getByTestId("task-card-t2");
    expect(within(card).getByLabelText("bloqueado")).toBeInTheDocument();
  });

  it("abrir documento mostra o conteúdo formatado", async () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    await userEvent.click(screen.getByTestId("doc-card-prd"));
    expect(await screen.findByTestId("markdown-viewer")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Hello PRD" })).toBeInTheDocument();
  });

  it("card de task tem handle visual de drag e abre pelo título", async () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    expect(screen.getByTestId("task-drag-handle-t1")).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("task-card-open-t1"));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("exibe Assumir no card de backlog sem responsável", () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    expect(screen.getByTestId("claim-card-t2")).toBeInTheDocument();
    expect(screen.queryByTestId("claim-card-t1")).not.toBeInTheDocument();
  });

  it("Assumir no card chama claimTask", async () => {
    claimTask.mockResolvedValue({ claimed: true, version: 2 });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    await userEvent.click(screen.getByTestId("claim-card-t2"));
    expect(claimTask).toHaveBeenCalledWith("t2", expect.any(String));
    await waitFor(() =>
      expect(fetchWorkspaceBoard).toHaveBeenCalledWith("ws-1"),
    );
  });

  it("botão Nova task abre diálogo e cria card", async () => {
    createTask.mockResolvedValue({
      id: "t-new",
      workspace_id: "ws-1",
      title: "Nova",
      status: "tasks",
      is_blocked: false,
      version: 1,
    });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);

    await userEvent.click(screen.getByTestId("create-task-btn"));
    await userEvent.type(screen.getByLabelText("Título"), "Card novo");
    await userEvent.click(screen.getByTestId("create-task-submit"));

    await waitFor(() =>
      expect(createTask).toHaveBeenCalledWith({
        workspace_id: "ws-1",
        title: "Card novo",
        description: null,
      }),
    );
    expect(fetchWorkspaceBoard).toHaveBeenCalledWith("ws-1");
  });

  it("abrir task e assumir com 409 exibe quem já assumiu", async () => {
    claimTask.mockResolvedValue({ claimed: false, current_assignee: "host-x" });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);

    await userEvent.click(screen.getByTestId("claim-card-t2"));

    expect(claimTask).toHaveBeenCalledWith("t2", expect.any(String));
    await waitFor(() => {
      const alerts = screen.getAllByRole("alert");
      expect(
        alerts.some((el) => /Já assumida por host-x/.test(el.textContent || "")),
      ).toBe(true);
    });
  });

  it("abrir task e assumir com sucesso ressincroniza o quadro", async () => {
    claimTask.mockResolvedValue({ claimed: true, version: 2 });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    await userEvent.click(
      within(screen.getByTestId("task-card-t2")).getByText("Card backlog"),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Assumir" }));
    await waitFor(() =>
      expect(fetchWorkspaceBoard).toHaveBeenCalledWith("ws-1"),
    );
  });

  it("abrir task e bloquear chama update_task_status", async () => {
    updateTaskStatus.mockResolvedValue({ conflict: false });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    await userEvent.click(
      within(screen.getByTestId("task-card-t1")).getByText("Card em andamento"),
    );
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Bloquear" }));
    await waitFor(() =>
      expect(updateTaskStatus).toHaveBeenCalledWith(
        "t1",
        expect.objectContaining({
          expected_version: 4,
          new_status: "em_andamento",
          is_blocked: true,
        }),
      ),
    );
    expect(fetchWorkspaceBoard).toHaveBeenCalledWith("ws-1");
  });

  it("polling reflete mudança de status feita por outro ator", async () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    store.dispatch(
      setCurrentBoard({
        ...board,
        tasks: board.tasks.map((t) =>
          t.id === "t2" ? { ...t, status: "revisao_codigo" } : t,
        ),
      }),
    );
    await waitFor(() => {
      const revisao = screen.getByTestId("column-revisao_codigo");
      expect(within(revisao).getByTestId("task-card-t2")).toBeInTheDocument();
    });
  });
});
