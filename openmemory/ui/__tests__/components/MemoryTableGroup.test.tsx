import React from "react";
import { render, screen } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

jest.mock("@/hooks/useMemoriesApi", () => ({
  useMemoriesApi: () => ({
    deleteMemories: jest.fn(),
    updateMemoryState: jest.fn(),
    isLoading: false,
    deletionPolicy: null,
  }),
}));
jest.mock("@/hooks/useUI", () => ({
  useUI: () => ({ handleOpenUpdateMemoryDialog: jest.fn() }),
}));
jest.mock("@/hooks/use-toast", () => ({ useToast: () => ({ toast: jest.fn() }) }));
jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

import memoriesReducer, { setMemoriesSuccess } from "@/store/memoriesSlice";
import { MemoryTable } from "@/app/memories/components/MemoryTable";
import type { Memory } from "@/components/types";

const memories: Memory[] = [
  {
    id: "m1",
    memory: "com grupo",
    metadata: {},
    client: "api",
    categories: [],
    created_at: Date.now(),
    app_name: "cli",
    state: "active",
    group: "Equipe A",
    created_by_hostname: "S0293",
    created_by_client: "cursor",
  },
  {
    id: "m2",
    memory: "sem grupo",
    metadata: {},
    client: "api",
    categories: [],
    created_at: Date.now(),
    app_name: "cli",
    state: "active",
    group: null,
  },
];

function renderTable() {
  const store = configureStore({ reducer: { memories: memoriesReducer } });
  store.dispatch(setMemoriesSuccess(memories));
  return render(
    <Provider store={store}>
      <MemoryTable />
    </Provider>,
  );
}

describe("MemoryTable — etiqueta de grupo (task_09)", () => {
  it("exibe o cabeçalho de Grupo", () => {
    renderTable();
    expect(screen.getByText("Grupo")).toBeInTheDocument();
  });

  it("renderiza o nome do grupo do autor", () => {
    renderTable();
    expect(screen.getByText("Equipe A")).toBeInTheDocument();
  });

  it("exibe o hostname do autor na coluna Criado por", () => {
    renderTable();
    expect(screen.getByText("S0293")).toBeInTheDocument();
  });

  it("usa rótulo neutro '—' para memória sem grupo", () => {
    renderTable();
    const labels = screen.getAllByLabelText("Grupo do autor");
    const texts = labels.map((el) => el.textContent);
    expect(texts).toContain("Equipe A");
    expect(texts).toContain("—");
  });
});
