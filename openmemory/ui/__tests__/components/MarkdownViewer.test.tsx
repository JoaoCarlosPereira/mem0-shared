import React from "react";
import { render, screen } from "@testing-library/react";
import { MarkdownViewer } from "@/components/shared/MarkdownViewer";

describe("MarkdownViewer", () => {
  it("renderiza headings e listas formatados", () => {
    render(
      <MarkdownViewer
        content={`# Título\n\nParágrafo com **negrito**.\n\n- item a\n- item b`}
      />,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Título" })).toBeInTheDocument();
    expect(screen.getByText("negrito")).toBeInTheDocument();
    expect(screen.getByText("item a")).toBeInTheDocument();
  });

  it("mostra label vazio quando não há conteúdo", () => {
    render(<MarkdownViewer content="   " emptyLabel="(vazio)" />);
    expect(screen.getByText("(vazio)")).toBeInTheDocument();
  });

  it("renderiza tabela GFM", () => {
    render(
      <MarkdownViewer
        content={`| Col A | Col B |\n| --- | --- |\n| 1 | 2 |`}
      />,
    );
    expect(screen.getByText("Col A")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });
});
