import React from "react";
import { render, screen } from "@testing-library/react";

const replace = jest.fn();

jest.mock("next/navigation", () => ({
  useParams: () => ({ project: "mem0-shared" }),
  useRouter: () => ({ replace }),
}));

import ProjectSpecsPanel from "@/app/docs/[project]/page";

describe("ProjectSpecsPanel redirect (ADR-008)", () => {
  beforeEach(() => {
    replace.mockReset();
  });

  it("redireciona /docs/[project] para home Kanban", () => {
    render(<ProjectSpecsPanel />);
    expect(replace).toHaveBeenCalledWith("/docs");
    expect(screen.getByText(/Redirecionando para Kanban/i)).toBeInTheDocument();
    expect(screen.queryByText(/Documentações/)).not.toBeInTheDocument();
  });
});
