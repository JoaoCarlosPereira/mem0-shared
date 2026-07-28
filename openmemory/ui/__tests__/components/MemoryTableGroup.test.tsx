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
import { groupCardTone, UNGROUPED_CARD_TONE } from "@/lib/group-card-tone";

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

describe("MemoryTable — cards por grupo", () => {
  it("renderiza cards clicáveis em vez de tabela com Categorias", () => {
    renderTable();
    expect(screen.queryByText("Categorias")).not.toBeInTheDocument();
    expect(screen.queryByText("Criado por")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /com grupo/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /sem grupo/i })).toBeInTheDocument();
  });

  it("marca data-group no card com o nome do grupo do autor", () => {
    renderTable();
    const withGroup = screen.getByRole("link", { name: /com grupo/i });
    expect(withGroup).toHaveAttribute("data-group", "Equipe A");
    const withoutGroup = screen.getByRole("link", { name: /sem grupo/i });
    expect(withoutGroup).toHaveAttribute("data-group", "");
  });

  it("exibe o autor só no aria-label do avatar (hint), não como texto da coluna", () => {
    renderTable();
    expect(screen.getByLabelText("Criado por S0293")).toBeInTheDocument();
    expect(screen.queryByText("S0293")).not.toBeInTheDocument();
  });

  it("aplica tom neutro quando não há grupo", () => {
    expect(groupCardTone(null)).toEqual(UNGROUPED_CARD_TONE);
    expect(groupCardTone("")).toEqual(UNGROUPED_CARD_TONE);
  });

  it("escolhe tom estável para o mesmo grupo", () => {
    expect(groupCardTone("Equipe A")).toEqual(groupCardTone("Equipe A"));
    expect(groupCardTone("Equipe A")).not.toEqual(groupCardTone("Equipe B"));
  });

  it("sem grupo varia pelo autor em vez de ficar sempre neutro", () => {
    expect(groupCardTone(null, "pop-os")).not.toEqual(
      groupCardTone(null, "outro-host"),
    );
    expect(groupCardTone(null, "pop-os")).toEqual(
      groupCardTone(null, "pop-os"),
    );
  });
});
