import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

jest.mock("next/navigation", () => ({
  useParams: () => ({ project: "mem0-shared" }),
}));

const deleteWorkspace = jest.fn();
const fetchProjectWorkspaces = jest.fn();
jest.mock("@/hooks/useSpecsApi", () => ({
  useSpecsApi: jest.fn(() => ({ deleteWorkspace, fetchProjectWorkspaces })),
}));

import specsReducer, {
  setProjectWorkspaces,
  setSpecsLoading,
  setSpecsError,
} from "@/store/specsSlice";
import ProjectSpecsPanel from "@/app/docs/[project]/page";
import type { WorkspaceSummary } from "@/types/specs";

const wsA: WorkspaceSummary = {
  id: "ws-aaa",
  project_id: "mem0-shared",
  slug: "feature-a",
  name: "Feature A",
  status: "ativo",
  task_counts: { tasks: 2, em_andamento: 1 },
};

function makeStore() {
  return configureStore({ reducer: { specs: specsReducer } });
}

function renderWith(store: ReturnType<typeof makeStore>) {
  return render(
    <Provider store={store}>
      <ProjectSpecsPanel />
    </Provider>,
  );
}

describe("ProjectSpecsPanel", () => {
  it("renderiza o cabeçalho do projeto", () => {
    renderWith(makeStore());
    expect(screen.getByText("Documentações — mem0-shared")).toBeInTheDocument();
  });

  it("lista as Tarefas com progresso resumido por coluna", () => {
    const store = makeStore();
    store.dispatch(setProjectWorkspaces([wsA]));
    renderWith(store);
    expect(screen.getByText("Feature A")).toBeInTheDocument();
    expect(screen.getByText("feature-a")).toBeInTheDocument();
    // contagem por coluna
    expect(screen.getByText(/Tasks:/)).toBeInTheDocument();
    expect(screen.getByText(/Em andamento:/)).toBeInTheDocument();
  });

  it("link da Tarefa aponta para a rota do quadro (integração painel → quadro)", () => {
    const store = makeStore();
    store.dispatch(setProjectWorkspaces([wsA]));
    renderWith(store);
    const link = screen.getByText("Feature A").closest("a");
    expect(link).toHaveAttribute(
      "href",
      "/docs/mem0-shared/ws-aaa",
    );
  });

  it("exibe carregando quando ainda não há dados", () => {
    const store = makeStore();
    store.dispatch(setSpecsLoading());
    renderWith(store);
    expect(screen.getByText("Carregando…")).toBeInTheDocument();
  });

  it("exibe estado vazio quando o projeto não tem Tarefas", () => {
    const store = makeStore();
    store.dispatch(setProjectWorkspaces([]));
    renderWith(store);
    expect(
      screen.getByText("Nenhuma Tarefa neste projeto"),
    ).toBeInTheDocument();
  });

  it("exibe erro quando o slice tem erro", () => {
    const store = makeStore();
    store.dispatch(setSpecsError("Falha ao listar workspaces"));
    renderWith(store);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Falha ao listar workspaces",
    );
  });

  it("botão excluir abre confirmação e chama deleteWorkspace + refetch", async () => {
    deleteWorkspace.mockReset().mockResolvedValue(undefined);
    fetchProjectWorkspaces.mockReset().mockResolvedValue(undefined);
    const store = makeStore();
    store.dispatch(setProjectWorkspaces([wsA]));
    renderWith(store);

    await userEvent.click(
      screen.getByRole("button", { name: "Excluir Feature A" }),
    );
    expect(
      await screen.findByText("Excluir Tarefa permanentemente?"),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Excluir Tarefa" }));
    await waitFor(() => expect(deleteWorkspace).toHaveBeenCalledWith("ws-aaa"));
    expect(fetchProjectWorkspaces).toHaveBeenCalledWith("mem0-shared");
  });
});
