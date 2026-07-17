import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const fetchGroups = jest.fn();
const fetchMemberCandidates = jest.fn();
const createGroup = jest.fn();
const updateGroup = jest.fn();
const deleteGroup = jest.fn();
const fetchMembers = jest.fn();
const addMember = jest.fn();
const removeMember = jest.fn();

jest.mock("@/hooks/useGroupsApi", () => ({
  useGroupsApi: () => ({
    fetchGroups,
    fetchMemberCandidates,
    createGroup,
    updateGroup,
    deleteGroup,
    fetchMembers,
    addMember,
    removeMember,
  }),
}));

import GroupsPage from "@/app/admin/groups/page";

beforeEach(() => {
  jest.clearAllMocks();
  fetchGroups.mockResolvedValue([
    { id: "g1", name: "Equipe A", member_count: 2 },
    { id: "g2", name: "Equipe B", member_count: 0 },
  ]);
  fetchMemberCandidates.mockResolvedValue([
    {
      id: "c1",
      user_id: "S0136",
      display_name: "Mauricio Spaniol",
      group_name: "Default",
    },
    {
      id: "c2",
      user_id: "host-a",
      display_name: "Ana Silva",
      group_name: "Equipe A",
    },
  ]);
  createGroup.mockResolvedValue({ id: "g3", name: "Nova", member_count: 0 });
});

describe("GroupsPage (task_08)", () => {
  it("lista grupos com a contagem de membros", async () => {
    render(<GroupsPage />);
    expect(await screen.findByText("Equipe A")).toBeInTheDocument();
    expect(screen.getByText("Equipe B")).toBeInTheDocument();
  });

  it("criar grupo chama createGroup e recarrega a lista", async () => {
    render(<GroupsPage />);
    await screen.findByText("Equipe A");

    fireEvent.change(screen.getByPlaceholderText("Nome do novo grupo…"), {
      target: { value: "Nova" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar grupo" }));

    await waitFor(() => expect(createGroup).toHaveBeenCalledWith("Nova"));
    // reload => fetchGroups chamado na montagem e após criar
    expect(fetchGroups).toHaveBeenCalledTimes(2);
  });

  it("exibe erro do backend (ex.: nome duplicado 409)", async () => {
    createGroup.mockRejectedValue({
      response: { data: { detail: "Group name already exists" } },
    });
    render(<GroupsPage />);
    await screen.findByText("Equipe A");

    fireEvent.change(screen.getByPlaceholderText("Nome do novo grupo…"), {
      target: { value: "Equipe A" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Criar grupo" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Group name already exists",
    );
  });

  it("abrir membros carrega e exibe a lista do grupo", async () => {
    fetchMembers.mockResolvedValue([
      {
        id: "u1",
        user_id: "host-a",
        name: null,
        display_name: "Ana Silva",
        avatar_url: null,
      },
    ]);
    render(<GroupsPage />);
    await screen.findByText("Equipe A");

    fireEvent.click(screen.getAllByRole("button", { name: "Membros" })[0]);

    await waitFor(() => expect(fetchMembers).toHaveBeenCalledWith("g1"));
    expect(fetchMemberCandidates).toHaveBeenCalled();
    expect(await screen.findByText("Ana Silva")).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: /buscar hostname ou nome/i }),
    ).toBeInTheDocument();
  });

  it("mover membro seleciona hostname existente via combobox", async () => {
    fetchMembers.mockResolvedValue([]);
    addMember.mockResolvedValue({
      id: "u2",
      user_id: "S0136",
      display_name: "Mauricio Spaniol",
    });
    render(<GroupsPage />);
    await screen.findByText("Equipe A");

    fireEvent.click(screen.getAllByRole("button", { name: "Membros" })[0]);
    await waitFor(() => expect(fetchMemberCandidates).toHaveBeenCalled());

    fireEvent.click(
      screen.getByRole("combobox", { name: /buscar hostname ou nome/i }),
    );
    fireEvent.click(await screen.findByText("Mauricio Spaniol"));
    fireEvent.click(screen.getByRole("button", { name: "Adicionar / mover" }));

    await waitFor(() =>
      expect(addMember).toHaveBeenCalledWith("g1", "S0136"),
    );
  });
});
