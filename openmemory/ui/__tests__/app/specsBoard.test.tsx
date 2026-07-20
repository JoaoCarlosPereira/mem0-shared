import React from "react";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

jest.mock("next/navigation", () => ({
  useParams: () => ({ project: "mem0-shared", workspace: "ws-1" }),
}));

const updateTaskStatus = jest.fn();
const claimTask = jest.fn();
const fetchWorkspaceBoard = jest.fn();
jest.mock("@/hooks/useSpecsApi", () => ({
  useSpecsApi: jest.fn(() => ({ updateTaskStatus, claimTask, fetchWorkspaceBoard })),
}));

import specsReducer, { setCurrentBoard } from "@/store/specsSlice";
import SpecsBoardPage from "@/app/admin/specs/[project]/[workspace]/page";
import type { WorkspaceBoard } from "@/types/specs";

const board: WorkspaceBoard = {
  workspace: { id: "ws-1", project_id: "mem0-shared", slug: "ws-1", name: "Feature A", status: "ativo" },
  documents: [
    { id: "d1", workspace_id: "ws-1", document_type: "prd", current_version: 2 },
  ],
  tasks: [
    {
      id: "t1",
      workspace_id: "ws-1",
      title: "Card em andamento",
      status: "em_andamento",
      is_blocked: false,
      assignee: "host-a",
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
  claimTask.mockReset();
  fetchWorkspaceBoard.mockReset();
});

describe("SpecsBoardPage", () => {
  it("renderiza as colunas fixas do sistema", () => {
    renderWith(makeStore());
    ["SDD", "Tasks", "Em andamento", "Revisão de código", "Fase de teste", "Concluído"].forEach(
      (label) => expect(screen.getByText(label)).toBeInTheDocument(),
    );
  });

  it("documento aparece na coluna SDD com a versão atual", () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const sdd = screen.getByTestId("column-SDD");
    expect(within(sdd).getByText("prd")).toBeInTheDocument();
    expect(within(sdd).getByText("versão v2")).toBeInTheDocument();
  });

  it("card de task exibe o responsável quando presente", () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const card = screen.getByTestId("task-card-t1");
    expect(within(card).getByText("host-a")).toBeInTheDocument();
  });

  it("card bloqueado exibe o badge de bloqueio", () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const card = screen.getByTestId("task-card-t2");
    expect(within(card).getByLabelText("bloqueado")).toBeInTheDocument();
  });

  it("claim que retorna 409 exibe quem já assumiu e desabilita o botão", async () => {
    claimTask.mockResolvedValue({ claimed: false, current_assignee: "host-x" });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);

    const card = screen.getByTestId("task-card-t2");
    await userEvent.click(within(card).getByRole("button", { name: "Assumir" }));

    expect(claimTask).toHaveBeenCalledWith("t2", expect.any(String));
    expect(await screen.findByText(/Já assumida por host-x/)).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Assumir" })).toBeDisabled();
  });

  it("claim bem-sucedido ressincroniza o quadro", async () => {
    claimTask.mockResolvedValue({ claimed: true, version: 2 });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const card = screen.getByTestId("task-card-t2");
    await userEvent.click(within(card).getByRole("button", { name: "Assumir" }));
    await waitFor(() => expect(fetchWorkspaceBoard).toHaveBeenCalledWith("ws-1"));
    expect(screen.queryByText(/Já assumida por/)).not.toBeInTheDocument();
  });

  it("alternar bloqueio chama update_task_status com is_blocked", async () => {
    updateTaskStatus.mockResolvedValue({ conflict: false });
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    const card = screen.getByTestId("task-card-t1"); // não bloqueado
    await userEvent.click(within(card).getByRole("button", { name: "Bloquear" }));
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

  it("polling reflete mudança de status feita por outro ator (re-render do slice)", async () => {
    const store = makeStore();
    store.dispatch(setCurrentBoard(board));
    renderWith(store);
    // t2 estava em "tasks"; outro ator moveu para "revisao_codigo".
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
