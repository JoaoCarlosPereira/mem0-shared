import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TaskRichFields } from "@/components/docs/TaskRichFields";
import type { TaskCard } from "@/types/specs";

const task: TaskCard = {
  id: "t1",
  workspace_id: "w1",
  title: "Card",
  status: "tasks",
  is_blocked: false,
  version: 1,
};

function makeApi(overrides: Record<string, jest.Mock> = {}) {
  return {
    listLabels: jest.fn().mockResolvedValue([
      { id: "l1", workspace_id: "w1", name: "bug", color: "#f00" },
    ]),
    listTaskLabels: jest.fn().mockResolvedValue([
      { id: "l1", workspace_id: "w1", name: "bug", color: "#f00" },
    ]),
    createLabel: jest.fn(),
    attachLabel: jest.fn().mockResolvedValue(task),
    detachLabel: jest.fn().mockResolvedValue(undefined),
    listChecklists: jest.fn().mockResolvedValue([
      {
        id: "c1",
        task_id: "t1",
        title: "QA",
        position: 1,
        items: [
          {
            id: "i1",
            checklist_id: "c1",
            title: "rodar testes",
            is_completed: false,
            position: 1,
          },
        ],
      },
    ]),
    createChecklist: jest.fn(),
    createChecklistItem: jest.fn(),
    patchChecklistItem: jest.fn().mockResolvedValue({}),
    listAttachments: jest.fn().mockResolvedValue([
      {
        id: "a1",
        task_id: "t1",
        filename: "note.txt",
        size_bytes: 4,
      },
    ]),
    uploadAttachment: jest.fn(),
    deleteAttachment: jest.fn(),
    attachmentDownloadUrl: jest.fn((id: string) => `/att/${id}`),
    ...overrides,
  };
}

describe("TaskRichFields", () => {
  it("renderiza labels/checklist e faz toggle de item", async () => {
    const api = makeApi();
    render(
      <TaskRichFields
        task={task}
        workspaceId="w1"
        api={api}
        dueAt=""
        membersText=""
        onDueAtChange={jest.fn()}
        onMembersTextChange={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("task-labels-list")).toHaveTextContent("bug");
    });
    expect(screen.getByTestId("task-checklists")).toHaveTextContent(
      "rodar testes",
    );
    expect(screen.getByTestId("task-attachments")).toHaveTextContent("note.txt");
    expect(api.listTaskLabels).toHaveBeenCalledWith("t1");
    expect(api.listAttachments).toHaveBeenCalledWith("t1");

    // label já reidratada como anexada → toggle faz detach
    fireEvent.click(screen.getByTestId("task-label-l1"));
    await waitFor(() => {
      expect(api.detachLabel).toHaveBeenCalledWith("t1", "l1");
    });

    fireEvent.click(screen.getByTestId("checklist-item-i1"));
    await waitFor(() => {
      expect(api.patchChecklistItem).toHaveBeenCalledWith("c1", "i1", {
        is_completed: true,
      });
    });
  });
});
