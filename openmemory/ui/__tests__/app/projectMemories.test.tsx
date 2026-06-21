import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

jest.mock("next/navigation", () => ({
  useParams: () => ({ project: "proj-a" }),
}));

const fetchProjectMemories = jest.fn();
jest.mock("@/hooks/useAdminApi", () => ({
  useAdminApi: jest.fn(() => ({ fetchProjectMemories })),
}));

import ProjectMemoriesPage from "@/app/admin/projects/[project]/page";
import type { ProjectMemoriesResponse } from "@/types/admin";

const page: ProjectMemoriesResponse = {
  project: "proj-a",
  items: [
    {
      id: "m1",
      memory: "conteúdo da memória um",
      created_at: "2026-01-01T10:00:00Z",
      project: "proj-a",
    },
  ],
  total: 1,
};

beforeEach(() => {
  fetchProjectMemories.mockReset().mockResolvedValue(page);
});

describe("ProjectMemoriesPage (leitura por projeto / Qdrant)", () => {
  it("exibe o cabeçalho do projeto e a lista de memórias", async () => {
    render(<ProjectMemoriesPage />);
    expect(screen.getByText("Memórias — proj-a")).toBeInTheDocument();
    expect(
      await screen.findByText("conteúdo da memória um"),
    ).toBeInTheDocument();
  });

  it("carrega memórias do projeto via fetchProjectMemories ao montar", async () => {
    render(<ProjectMemoriesPage />);
    await waitFor(() =>
      expect(fetchProjectMemories).toHaveBeenCalledWith("proj-a", undefined),
    );
  });

  it("busca aciona fetchProjectMemories com o termo digitado", async () => {
    render(<ProjectMemoriesPage />);
    await screen.findByText("conteúdo da memória um");
    const input = screen.getByPlaceholderText(/Buscar memórias/i);
    await userEvent.type(input, "reunião");
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }));
    await waitFor(() =>
      expect(fetchProjectMemories).toHaveBeenLastCalledWith("proj-a", "reunião"),
    );
  });

  it("exibe estado vazio quando não há memórias", async () => {
    fetchProjectMemories.mockResolvedValue({
      project: "proj-a",
      items: [],
      total: 0,
    });
    render(<ProjectMemoriesPage />);
    expect(
      await screen.findByText("Nenhuma memória encontrada neste projeto"),
    ).toBeInTheDocument();
  });
});
