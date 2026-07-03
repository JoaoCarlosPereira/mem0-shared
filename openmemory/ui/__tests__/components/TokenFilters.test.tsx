import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

import { TokenFilters } from "@/components/metrics/TokenFilters";
import type { MetricsFilters } from "@/types/metrics";

const baseFilters: MetricsFilters = {
  start: "2026-06-01T00:00:00",
  granularity: "project",
};

describe("TokenFilters", () => {
  it("propaga filtros somente ao clicar em Aplicar", () => {
    const onChange = jest.fn();
    render(<TokenFilters filters={baseFilters} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Projeto"), {
      target: { value: "proj-x" },
    });
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        start: "2026-06-01T00:00:00",
        project: "proj-x",
        granularity: "project",
      }),
    );
  });

  it("converte datas do input para ISO com hora", () => {
    const onChange = jest.fn();
    render(<TokenFilters filters={baseFilters} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Início"), {
      target: { value: "2026-06-10" },
    });
    fireEvent.change(screen.getByLabelText("Fim"), {
      target: { value: "2026-06-20" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        start: "2026-06-10T00:00:00",
        end: "2026-06-20T23:59:59",
      }),
    );
  });

  it("mapeia operação selecionada para array operation_type", () => {
    const onChange = jest.fn();
    render(<TokenFilters filters={baseFilters} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Operação"), {
      target: { value: "search" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));

    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ operation_type: ["search"] }),
    );
  });

  it("não aplica sem data de início", () => {
    const onChange = jest.fn();
    render(<TokenFilters filters={baseFilters} onChange={onChange} />);

    fireEvent.change(screen.getByLabelText("Início"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
