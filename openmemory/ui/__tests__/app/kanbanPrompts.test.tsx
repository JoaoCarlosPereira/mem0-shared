import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import KanbanPromptsPage from "@/app/admin/kanban-prompts/page";
import { useAdminApi } from "@/hooks/useAdminApi";
import type { KanbanPrompt } from "@/types/admin";

jest.mock("@/hooks/useAdminApi");

const mockedUseAdminApi = useAdminApi as jest.MockedFunction<typeof useAdminApi>;

const prompts: KanbanPrompt[] = [
  {
    column_status: "tasks",
    label: "Backlog (Tasks)",
    prompt: "Prompt backlog",
    is_enabled: true,
    updated_at: null,
    updated_by: null,
  },
  {
    column_status: "em_andamento",
    label: "Em andamento",
    prompt: "Prompt andamento",
    is_enabled: true,
    updated_at: null,
    updated_by: null,
  },
];

describe("KanbanPromptsPage", () => {
  const fetchKanbanPrompts = jest.fn();
  const updateKanbanPrompt = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    fetchKanbanPrompts.mockResolvedValue(prompts);
    updateKanbanPrompt.mockImplementation(async (status, updates) => ({
      ...prompts.find((prompt) => prompt.column_status === status)!,
      ...updates,
      column_status: status,
    }));
    mockedUseAdminApi.mockReturnValue({
      fetchAdminOverview: jest.fn(),
      fetchWriteAudit: jest.fn(),
      fetchProjectSizes: jest.fn(),
      fetchProjectMemories: jest.fn(),
      fetchKanbanPrompts,
      updateKanbanPrompt,
    });
  });

  it("edita e salva somente a coluna cujo textarea perdeu o foco", async () => {
    render(<KanbanPromptsPage />);

    await waitFor(() => expect(screen.getByDisplayValue("Prompt backlog")).toBeInTheDocument());
    const textareas = screen.getAllByRole("textbox");

    fireEvent.change(textareas[0], { target: { value: "Prompt backlog alterado" } });
    expect(screen.getByDisplayValue("Prompt backlog alterado")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Prompt andamento")).toBeInTheDocument();
    expect(updateKanbanPrompt).not.toHaveBeenCalled();

    fireEvent.blur(textareas[0]);

    await waitFor(() => {
      expect(updateKanbanPrompt).toHaveBeenCalledWith("tasks", { prompt: "Prompt backlog alterado" });
    });
    expect(updateKanbanPrompt).toHaveBeenCalledTimes(1);
  });

  it("salva o switch usando o column_status correto", async () => {
    render(<KanbanPromptsPage />);

    await waitFor(() => expect(screen.getByDisplayValue("Prompt andamento")).toBeInTheDocument());
    const switches = screen.getAllByRole("switch");

    fireEvent.click(switches[1]);

    await waitFor(() => {
      expect(updateKanbanPrompt).toHaveBeenCalledWith("em_andamento", { is_enabled: false });
    });
  });
});
