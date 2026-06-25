import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

const fetchWriteAudit = jest.fn();
const fetchProjectSizes = jest.fn();
jest.mock("@/hooks/useAdminApi", () => ({
  useAdminApi: jest.fn(() => ({
    fetchWriteAudit,
    fetchProjectSizes,
    fetchAdminOverview: jest.fn(),
  })),
}));

import AuditPage from "@/app/admin/audit/page";
import { useAdminApi } from "@/hooks/useAdminApi";
import type { WriteAuditLog } from "@/types/admin";

const auditItem: WriteAuditLog = {
  id: "a1",
  job_id: "j1",
  project: "proj-a",
  hostname: "host-1",
  client_name: "cli-x",
  action: "enqueue",
  created_at: "2026-01-02T08:30:00Z",
};

beforeEach(() => {
  (useAdminApi as jest.Mock).mockClear();
  fetchWriteAudit.mockReset().mockResolvedValue({
    items: [auditItem],
    total: 1,
    page: 1,
    pages: 1,
  });
  fetchProjectSizes.mockReset().mockResolvedValue({
    threshold: 0,
    over_threshold_count: 0,
    projects: [
      {
        name: "proj-a",
        memory_count: 1,
        partition_tier: "shared",
        shard_key: null,
        over_threshold: false,
      },
    ],
  });
  mockedAxios.get.mockReset();
  (URL as any).createObjectURL = jest.fn(() => "blob:fake");
  (URL as any).revokeObjectURL = jest.fn();
  jest
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {});
});

afterEach(() => {
  jest.restoreAllMocks();
});

describe("AuditPage", () => {
  it("renderiza tabela com colunas e dados", async () => {
    render(<AuditPage />);
    expect(
      screen.getByRole("columnheader", { name: "Cliente" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Projeto" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Ação" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Data/Hora" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("cli-x")).toBeInTheDocument();
  });

  it("não inicia polling (useAdminApi chamado com poll:false)", () => {
    render(<AuditPage />);
    expect(useAdminApi).toHaveBeenCalledWith({ poll: false });
  });

  it("formata a data no padrão dd/MM/yyyy HH:mm:ss", async () => {
    render(<AuditPage />);
    expect(await screen.findByText("02/01/2026 05:30:00")).toBeInTheDocument();
  });

  it("exporta CSV com header Accept text/csv e responseType blob", async () => {
    mockedAxios.get.mockResolvedValue({ data: new Blob(["csv"]) });
    render(<AuditPage />);
    await screen.findByText("cli-x");
    await userEvent.click(screen.getByRole("button", { name: /Exportar CSV/i }));
    await waitFor(() =>
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining("/admin/write-audit"),
        expect.objectContaining({
          headers: { Accept: "text/csv" },
          responseType: "blob",
        }),
      ),
    );
  });

  it("exibe mensagem de erro quando o backend retorna 400", async () => {
    mockedAxios.get.mockRejectedValue({ response: { status: 400 } });
    render(<AuditPage />);
    await screen.findByText("cli-x");
    await userEvent.click(screen.getByRole("button", { name: /Exportar CSV/i }));
    expect(
      await screen.findByText(
        "Refine os filtros — mais de 10.000 registros selecionados",
      ),
    ).toBeInTheDocument();
  });

  it("filtro de hostname dispara novo fetchWriteAudit", async () => {
    render(<AuditPage />);
    await screen.findByText("cli-x");
    fetchWriteAudit.mockClear();
    const input = screen.getByLabelText("Filtrar por hostname");
    await userEvent.type(input, "host-9");
    await userEvent.tab();
    await waitFor(() =>
      expect(fetchWriteAudit).toHaveBeenCalledWith(
        expect.objectContaining({ hostname: "host-9" }),
      ),
    );
  });
});
