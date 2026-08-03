import React from "react";
import { render, screen } from "@testing-library/react";

const replace = jest.fn();

jest.mock("next/navigation", () => ({
  useParams: () => ({ project: "mem0-shared", workspace: "ws-1" }),
  useRouter: () => ({ replace }),
}));

import SpecsBoardPage from "@/app/docs/[project]/[workspace]/page";

describe("SpecsBoardPage redirect (ADR-008)", () => {
  beforeEach(() => {
    replace.mockReset();
  });

  it("redireciona rotas Spec antigas para /docs (home Kanban)", () => {
    render(<SpecsBoardPage />);
    expect(replace).toHaveBeenCalledWith("/docs");
    expect(screen.getByText(/Redirecionando para Kanban/i)).toBeInTheDocument();
    expect(screen.queryByTestId("column-SDD")).not.toBeInTheDocument();
  });
});
