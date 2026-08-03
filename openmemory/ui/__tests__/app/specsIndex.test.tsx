import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("@/hooks/useSpecsApi", () => ({
  useSpecsApi: jest.fn(() => ({})),
}));

jest.mock("@/components/docs/KanbanHomeCanvas", () => ({
  KanbanHomeCanvas: () => <div data-testid="kanban-home-canvas">kanban-home</div>,
}));

import SpecsIndexPage from "@/app/docs/page";

describe("KanbanHomePage (ADR-008)", () => {
  it("renderiza o canvas Kanban full-bleed (sem listagem Spec)", () => {
    render(<SpecsIndexPage />);
    expect(screen.getByTestId("kanban-home-canvas")).toBeInTheDocument();
    expect(screen.queryByText("Documentações")).not.toBeInTheDocument();
    expect(screen.queryByText(/Nenhuma spec ainda/)).not.toBeInTheDocument();
  });
});
