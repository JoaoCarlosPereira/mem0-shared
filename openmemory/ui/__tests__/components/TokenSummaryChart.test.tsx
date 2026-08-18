import React from "react";
import { render, screen } from "@testing-library/react";

// Mock Recharts components used by TokenSummaryChart.
jest.mock("recharts", () => {
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  );
  return {
    ResponsiveContainer: Passthrough,
    AreaChart: Passthrough,
    CartesianGrid: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    Legend: () => <div data-testid="legend" />,
    Area: ({ name }: { name: string }) => (
      <div data-testid={`area-${name}`} />
    ),
  };
});

import { TokenSummaryChart } from "@/components/metrics/TokenSummaryChart";
import type { TokenSummaryRow } from "@/types/metrics";

function row(overrides: Partial<TokenSummaryRow> = {}): TokenSummaryRow {
  return {
    period: "2026-06-01",
    group: "proj-a",
    input_tokens: 100,
    output_tokens: 50,
    total_tokens: 150,
    operation_count: 2,
    avg_tokens_per_op: 75,
    ...overrides,
  };
}

describe("TokenSummaryChart", () => {
  it("mostra empty state sem dados", () => {
    render(<TokenSummaryChart data={[]} />);
    expect(
      screen.getByText("Sem dados para o período selecionado."),
    ).toBeInTheDocument();
  });

  it("renderiza tiles com totais agregados do período", () => {
    render(
      <TokenSummaryChart
        data={[
          row(),
          row({
            period: "2026-06-02",
            input_tokens: 200,
            output_tokens: 100,
            total_tokens: 300,
            operation_count: 3,
          }),
        ]}
      />,
    );
    expect(screen.getByText("Total de tokens")).toBeInTheDocument();
    expect(screen.getByText("450")).toBeInTheDocument(); // 150 + 300
    expect(screen.getByText("300")).toBeInTheDocument(); // entrada 100 + 200
    expect(screen.getByText("5")).toBeInTheDocument(); // operações 2 + 3
    expect(screen.getByText("90")).toBeInTheDocument(); // média 450/5
  });

  it("cria uma série por grupo", () => {
    render(
      <TokenSummaryChart
        data={[row(), row({ group: "proj-b", total_tokens: 80 })]}
      />,
    );
    expect(screen.getByTestId("area-proj-a")).toBeInTheDocument();
    expect(screen.getByTestId("area-proj-b")).toBeInTheDocument();
    expect(screen.getByTestId("legend")).toBeInTheDocument();
  });

  it("agrega grupos além do teto em 'Outros'", () => {
    const groups = ["a", "b", "c", "d", "e", "f", "g"]; // more than SERIES_COLORS length (5)
    render(
      <TokenSummaryChart
        data={groups.map((g, i) =>
          row({ group: g, total_tokens: 1000 - i * 100 }),
        )}
      />,
    );
    expect(screen.getByTestId("area-Outros")).toBeInTheDocument();
    expect(screen.queryByTestId("area-g")).not.toBeInTheDocument();
  });

  it("exibe legenda também para série única", () => {
    render(<TokenSummaryChart data={[row()]} />);
    expect(screen.getByTestId("legend")).toBeInTheDocument();
  });
});
