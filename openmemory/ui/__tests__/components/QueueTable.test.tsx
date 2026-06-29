import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueueTable, QueueColumn } from "@/components/admin/QueueTable";
import { JobStatusBadge } from "@/components/admin/JobStatusBadge";

type Row = { id: string; name: string };
const columns: QueueColumn<Row>[] = [
  { key: "name", header: "Nome", render: (r) => r.name },
];

describe("JobStatusBadge", () => {
  it("status=failed renderiza com classe vermelha", () => {
    render(<JobStatusBadge status="failed" />);
    const badge = screen.getByText("Falhou");
    expect(badge).toHaveClass("bg-red-600");
  });

  it("status=done renderiza com classe verde", () => {
    render(<JobStatusBadge status="done" />);
    expect(screen.getByText("Concluído")).toHaveClass("bg-green-600");
  });
});

describe("QueueTable", () => {
  it("data=[] exibe mensagem de vazio", () => {
    render(
      <QueueTable
        columns={columns}
        data={[]}
        page={1}
        pages={0}
        onPageChange={() => {}}
      />,
    );
    expect(screen.getByText("Nenhum job encontrado")).toBeInTheDocument();
  });

  it("renderiza uma linha por item", () => {
    const data: Row[] = Array.from({ length: 5 }, (_, i) => ({
      id: String(i),
      name: `item-${i}`,
    }));
    render(
      <QueueTable
        columns={columns}
        data={data}
        page={1}
        pages={1}
        onPageChange={() => {}}
      />,
    );
    data.forEach((r) => expect(screen.getByText(r.name)).toBeInTheDocument());
  });

  it("clicar em 'Próxima página' chama onPageChange com page+1", async () => {
    const onPageChange = jest.fn();
    render(
      <QueueTable
        columns={columns}
        data={[{ id: "1", name: "a" }]}
        page={1}
        pages={3}
        onPageChange={onPageChange}
      />,
    );
    await userEvent.click(screen.getByText("Próxima página"));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});
