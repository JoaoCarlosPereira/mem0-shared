import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const fetchProjectSizes = jest.fn();
jest.mock("@/hooks/useAdminApi", () => ({
  useAdminApi: jest.fn(() => ({ fetchProjectSizes })),
}));

import ProjectsPage from "@/app/admin/projects/page";

beforeEach(() => {
  mockPush.mockReset();
  fetchProjectSizes.mockReset();
  fetchProjectSizes.mockResolvedValue({
    threshold: 1000,
    over_threshold_count: 0,
    projects: [
      {
        name: "proj-a",
        memory_count: 12,
        partition_tier: "shared",
        shard_key: null,
        over_threshold: false,
        last_activity_at: null,
      },
      {
        name: "proj-b",
        memory_count: 5000,
        partition_tier: "dedicated",
        shard_key: "proj-b",
        over_threshold: true,
        last_activity_at: null,
      },
    ],
  });
});

describe("ProjectsPage", () => {
  it("renderiza tabela com nome, contagem e tier", async () => {
    render(<ProjectsPage />);
    expect(await screen.findByText("proj-a")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("shared")).toBeInTheDocument();
    expect(screen.getByText("proj-b")).toBeInTheDocument();
    expect(screen.getByText("dedicated")).toBeInTheDocument();
  });

  it("clicar em um projeto navega para /admin/projects/[project]", async () => {
    render(<ProjectsPage />);
    const row = await screen.findByText("proj-a");
    await userEvent.click(row);
    await waitFor(() =>
      expect(mockPush).toHaveBeenCalledWith("/admin/projects/proj-a"),
    );
  });
});
