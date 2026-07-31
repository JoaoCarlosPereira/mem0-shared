import React from "react";
import { render, screen } from "@testing-library/react";
import { MarkdownViewer } from "@/components/shared/MarkdownViewer";
import { adrHeadingId, adrHrefToAnchor } from "@/lib/markdownAdrLinks";

describe("markdownAdrLinks", () => {
  it("converte hrefs legados adrs/*.md em âncora #adr-NNN", () => {
    expect(adrHrefToAnchor("adrs/adr-007.md")).toBe("#adr-007");
    expect(adrHrefToAnchor("../adrs/adr-013.md")).toBe("#adr-013");
    expect(adrHrefToAnchor("./adrs/adr-001.md#sec")).toBe("#adr-001");
    expect(adrHrefToAnchor("https://example.com/x")).toBeNull();
    expect(adrHrefToAnchor("/docs/foo")).toBeNull();
  });

  it("extrai id estável de headings ADR", () => {
    expect(adrHeadingId("ADR-007: Repositório")).toBe("adr-007");
    expect(adrHeadingId("ADR-013: Testes")).toBe("adr-013");
    expect(adrHeadingId("Outro título")).toBeUndefined();
  });
});

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

  it("não deixa links adrs/*.md como href relativo navegável", () => {
    render(
      <MarkdownViewer
        content={`- [ADR-007: Título](adrs/adr-007.md) — resumo\n\n### ADR-007: Título\n\n**Decisão**\nfazer X`}
      />,
    );
    const link = screen.getByRole("link", { name: /ADR-007/i });
    expect(link).toHaveAttribute("href", "#adr-007");
    expect(link.getAttribute("href")).not.toMatch(/adrs\/adr-007\.md/);
    expect(screen.getByRole("heading", { level: 3, name: /ADR-007/ })).toHaveAttribute(
      "id",
      "adr-007",
    );
  });

  it("chama onAdrLink ao clicar em adrs/*.md", () => {
    const onAdrLink = jest.fn();
    render(
      <MarkdownViewer
        content={`[ADR-007](adrs/adr-007.md)`}
        onAdrLink={onAdrLink}
      />,
    );
    screen.getByRole("link", { name: /ADR-007/i }).click();
    expect(onAdrLink).toHaveBeenCalledWith("adr-007");
  });
});
