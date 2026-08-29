import React from "react";
import { render, screen } from "@testing-library/react";

jest.mock("recharts", () => {
  const Passthrough = ({ children }: { children?: React.ReactNode }) => (
    <div>{children}</div>
  );
  return {
    ResponsiveContainer: Passthrough,
    BarChart: ({ children }: { children?: React.ReactNode }) => (
      <div data-testid="bar-chart">{children}</div>
    ),
    CartesianGrid: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    Bar: () => <div data-testid="bar-series" />,
  };
});

import { TopContributorsChart } from "@/components/admin/TopContributorsChart";
import type { TopContributor } from "@/types/admin";

function contributor(overrides: Partial<TopContributor> = {}): TopContributor {
  return {
    rank: 1,
    user_id: "alice-pc",
    display_name: "Alice",
    avatar_url: null,
    group_id: "group-1",
    group_name: "Dev",
    value: 10,
    writes: 7,
    reads: 3,
    distinct_projects: 2,
    ...overrides,
  };
}

describe("TopContributorsChart", () => {
  it("mostra empty state sem dados", () => {
    render(<TopContributorsChart items={[]} metric="total" />);
    expect(
      screen.getByText("Nenhuma contribuição no período"),
    ).toBeInTheDocument();
  });

  it("renderiza gráfico com dados", () => {
    render(
      <TopContributorsChart
        items={[contributor(), contributor({ rank: 2, user_id: "bob-pc", display_name: "Bob", value: 5 })]}
        metric="writes"
      />,
    );
    expect(screen.getByText("Top 10 contribuidores")).toBeInTheDocument();
    expect(screen.getByTestId("bar-chart")).toBeInTheDocument();
    expect(screen.getByTestId("bar-series")).toBeInTheDocument();
  });

  it("mostra skeleton durante loading", () => {
    const { container } = render(
      <TopContributorsChart items={[]} metric="total" loading />,
    );
    expect(container.querySelector(".animate-pulse")).toBeInTheDocument();
  });
});
