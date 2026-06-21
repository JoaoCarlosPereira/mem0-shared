import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Memory } from "@/components/types";

jest.mock("next/navigation", () => ({
  useParams: () => ({ project: "proj-a" }),
}));

const fetchMemories = jest.fn();
const createMemory = jest.fn();
const deleteMemories = jest.fn();
const updateMemoryState = jest.fn();

jest.mock("@/hooks/useMemoriesApi", () => ({
  useMemoriesApi: jest.fn(() => ({
    fetchMemories,
    createMemory,
    deleteMemories,
    updateMemoryState,
  })),
}));
jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

import ProjectMemoriesPage from "@/app/admin/projects/[project]/page";

const sampleMemories: Memory[] = [
  {
    id: "m1",
    memory: "conteúdo da memória um",
    metadata: {},
    client: "api",
    categories: [],
    created_at: 1700000000000,
    app_name: "openmemory",
    state: "active",
  },
];

function renderPage() {
  return render(<ProjectMemoriesPage />);
}

beforeEach(() => {
  fetchMemories.mockReset().mockResolvedValue({
    memories: sampleMemories,
    total: 1,
    pages: 1,
  });
  createMemory.mockReset().mockResolvedValue(undefined);
  deleteMemories.mockReset().mockResolvedValue(undefined);
  updateMemoryState.mockReset().mockResolvedValue(undefined);
});

describe("ProjectMemoriesPage", () => {
  it("exibe a lista de memórias do projeto", async () => {
    renderPage();
    expect(await screen.findByText("conteúdo da memória um")).toBeInTheDocument();
    expect(screen.getByText("Memórias — proj-a")).toBeInTheDocument();
  });

  it("busca chama fetchMemories com o search_query digitado", async () => {
    renderPage();
    const input = await screen.findByPlaceholderText("Buscar memórias…");
    await userEvent.type(input, "reunião");
    await waitFor(() =>
      expect(fetchMemories).toHaveBeenLastCalledWith(
        "reunião",
        1,
        10,
        expect.anything(),
      ),
    );
  });

  it("selecionar checkbox exibe botão 'Deletar selecionados'", async () => {
    renderPage();
    const cb = await screen.findByLabelText("Selecionar m1");
    await userEvent.click(cb);
    expect(
      screen.getByText(/Deletar selecionados/i),
    ).toBeInTheDocument();
  });

  it("delete pede confirmação antes de executar e remove após confirmar", async () => {
    renderPage();
    await screen.findByText("conteúdo da memória um");
    await userEvent.click(screen.getByLabelText("Deletar"));

    // Dialog de confirmação aparece e nada foi deletado ainda
    expect(screen.getByText("Confirmar exclusão")).toBeInTheDocument();
    expect(deleteMemories).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Sim, deletar" }));
    await waitFor(() =>
      expect(deleteMemories).toHaveBeenCalledWith(["m1"]),
    );
    await waitFor(() =>
      expect(
        screen.queryByText("conteúdo da memória um"),
      ).not.toBeInTheDocument(),
    );
  });

  it("modal de criação abre ao clicar em 'Nova Memória' e não cria sozinho", async () => {
    renderPage();
    await screen.findByText("conteúdo da memória um");
    await userEvent.click(screen.getByRole("button", { name: "Nova Memória" }));
    expect(screen.getByText("Nova Memória em proj-a")).toBeInTheDocument();
    expect(createMemory).not.toHaveBeenCalled();
  });
});
