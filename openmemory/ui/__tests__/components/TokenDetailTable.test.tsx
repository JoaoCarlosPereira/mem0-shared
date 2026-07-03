import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

const mockFetchDetails = jest.fn();
const mockState: {
  details: unknown;
  loading: boolean;
  error: string | null;
} = { details: null, loading: false, error: null };

jest.mock("@/hooks/useMetricsApi", () => ({
  useMetricsApi: () => ({
    details: mockState.details,
    loading: mockState.loading,
    error: mockState.error,
    fetchDetails: mockFetchDetails,
  }),
}));

import { TokenDetailTable } from "@/components/metrics/TokenDetailTable";
import type { MetricsFilters, TokenDetailsResponse } from "@/types/metrics";

const filters: MetricsFilters = {
  start: "2026-06-01T00:00:00",
  granularity: "project",
};

function details(overrides: Partial<TokenDetailsResponse> = {}): TokenDetailsResponse {
  return {
    total: 120,
    page: 1,
    page_size: 50,
    data: [
      {
        id: "row-1",
        created_at: "2026-06-01T10:00:00",
        project: "proj-a",
        agent: "claude",
        user_id: "host-1",
        operation_type: "add",
        model: "qwen3",
        input_tokens: 100,
        output_tokens: 40,
        total_tokens: 140,
        cache_read_tokens: 0,
        cache_write_tokens: 0,
        duration_ms: 800,
        success: true,
        error: null,
        trace_id: null,
      },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  mockFetchDetails.mockReset();
  mockState.details = null;
  mockState.loading = false;
  mockState.error = null;
});

describe("TokenDetailTable", () => {
  it("busca a primeira página ao montar", () => {
    render(<TokenDetailTable filters={filters} />);
    expect(mockFetchDetails).toHaveBeenCalledWith(
      filters,
      expect.objectContaining({
        page: 1,
        sortBy: "created_at",
        sortOrder: "desc",
      }),
    );
  });

  it("renderiza linhas e paginação com dados", () => {
    mockState.details = details();
    render(<TokenDetailTable filters={filters} />);
    expect(screen.getByText("proj-a")).toBeInTheDocument();
    expect(screen.getByText("claude")).toBeInTheDocument();
    expect(screen.getByText(/página 1 de 3/)).toBeInTheDocument();
  });

  it("avança para a próxima página", () => {
    mockState.details = details();
    render(<TokenDetailTable filters={filters} />);
    mockFetchDetails.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Próxima" }));
    expect(mockFetchDetails).toHaveBeenCalledWith(
      filters,
      expect.objectContaining({ page: 2 }),
    );
  });

  it("ordena ao clicar no cabeçalho e inverte no segundo clique", () => {
    mockState.details = details();
    render(<TokenDetailTable filters={filters} />);
    mockFetchDetails.mockClear();

    fireEvent.click(screen.getByRole("button", { name: /^Total/ }));
    expect(mockFetchDetails).toHaveBeenLastCalledWith(
      filters,
      expect.objectContaining({ sortBy: "total_tokens", sortOrder: "desc" }),
    );

    fireEvent.click(screen.getByRole("button", { name: /^Total/ }));
    expect(mockFetchDetails).toHaveBeenLastCalledWith(
      filters,
      expect.objectContaining({ sortBy: "total_tokens", sortOrder: "asc" }),
    );
  });

  it("mostra empty state quando não há registros", () => {
    mockState.details = details({ total: 0, data: [] });
    render(<TokenDetailTable filters={filters} />);
    expect(
      screen.getByText("Sem dados para o período selecionado."),
    ).toBeInTheDocument();
  });

  it("mostra erro com botão de retry quando fetch falha", () => {
    mockState.error = "falhou";
    render(<TokenDetailTable filters={filters} />);
    expect(screen.getByText("falhou")).toBeInTheDocument();
    mockFetchDetails.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    expect(mockFetchDetails).toHaveBeenCalled();
  });
});
