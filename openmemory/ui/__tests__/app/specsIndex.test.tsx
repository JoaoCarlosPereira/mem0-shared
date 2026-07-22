import React from "react";
import { render, screen, within } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

jest.mock("@/hooks/useSpecsApi", () => ({
  useSpecsApi: jest.fn(() => ({})),
}));

import specsReducer, { setAllWorkspaces, setSpecsLoading } from "@/store/specsSlice";
import SpecsIndexPage from "@/app/admin/specs/page";
import type { WorkspaceSummary } from "@/types/specs";

const wsA: WorkspaceSummary = {
  id: "ws-a",
  project_id: "proj-a",
  slug: "feature-a",
  name: "Feature A",
  status: "ativo",
  task_counts: { tasks: 2, em_andamento: 1 },
};
const wsB: WorkspaceSummary = {
  id: "ws-b",
  project_id: "proj-b",
  slug: "feature-b",
  name: "Feature B",
  status: "concluido",
  task_counts: {},
};

function makeStore() {
  return configureStore({ reducer: { specs: specsReducer } });
}

function renderWith(store: ReturnType<typeof makeStore>) {
  return render(
    <Provider store={store}>
      <SpecsIndexPage />
    </Provider>,
  );
}

describe("SpecsIndexPage", () => {
  it("renderiza o cabeçalho de Specs", () => {
    renderWith(makeStore());
    expect(screen.getByText("Specs")).toBeInTheDocument();
  });

  it("agrupa os quadros por projeto", () => {
    const store = makeStore();
    store.dispatch(setAllWorkspaces([wsA, wsB]));
    renderWith(store);
    expect(screen.getByText("proj-a")).toBeInTheDocument();
    expect(screen.getByText("proj-b")).toBeInTheDocument();
    expect(screen.getByText("Feature A")).toBeInTheDocument();
    expect(screen.getByText("Feature B")).toBeInTheDocument();
  });

  it("cada quadro linka para a rota do Kanban (índice → quadro)", () => {
    const store = makeStore();
    store.dispatch(setAllWorkspaces([wsA]));
    renderWith(store);
    const card = screen.getByTestId("spec-card-ws-a");
    expect(card).toHaveAttribute("href", "/admin/specs/proj-a/ws-a");
  });

  it("link 'ver painel' aponta para o painel do projeto", () => {
    const store = makeStore();
    store.dispatch(setAllWorkspaces([wsA]));
    renderWith(store);
    const painel = screen.getByRole("link", { name: "ver painel" });
    expect(painel).toHaveAttribute("href", "/admin/specs/proj-a");
  });

  it("estado vazio orienta a criar specs pelas skills", () => {
    const store = makeStore();
    store.dispatch(setAllWorkspaces([]));
    renderWith(store);
    expect(screen.getByText(/Nenhuma spec ainda/)).toBeInTheDocument();
  });

  it("exibe carregando antes dos dados", () => {
    const store = makeStore();
    store.dispatch(setSpecsLoading());
    renderWith(store);
    expect(screen.getByText("Carregando…")).toBeInTheDocument();
  });
});
