import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryStateActions } from "@/components/admin/MemoryStateActions";

function setup(state: "active" | "archived") {
  const handlers = {
    onPause: jest.fn(),
    onArchive: jest.fn(),
    onReactivate: jest.fn(),
    onDelete: jest.fn(),
  };
  render(<MemoryStateActions state={state} {...handlers} />);
  return handlers;
}

describe("MemoryStateActions", () => {
  it("state=active exibe Pausar e Arquivar", () => {
    setup("active");
    expect(screen.getByLabelText("Pausar")).toBeInTheDocument();
    expect(screen.getByLabelText("Arquivar")).toBeInTheDocument();
    expect(screen.queryByLabelText("Reativar")).not.toBeInTheDocument();
  });

  it("state=archived exibe Reativar (sem Pausar/Arquivar)", () => {
    setup("archived");
    expect(screen.getByLabelText("Reativar")).toBeInTheDocument();
    expect(screen.queryByLabelText("Pausar")).not.toBeInTheDocument();
  });

  it("clicar em Deletar chama onDelete", async () => {
    const handlers = setup("active");
    await userEvent.click(screen.getByLabelText("Deletar"));
    expect(handlers.onDelete).toHaveBeenCalled();
  });
});
