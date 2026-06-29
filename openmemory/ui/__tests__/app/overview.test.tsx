import React from "react";
import { render, screen } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

jest.mock("@/hooks/useAdminApi", () => ({
  useAdminApi: jest.fn(() => ({
    fetchAdminOverview: jest.fn(),
    fetchWriteAudit: jest.fn(),
    fetchProjectSizes: jest.fn(),
  })),
}));

import adminReducer, { setAdminOverview } from "@/store/adminSlice";
import queuesReducer, { setFailedJobIds } from "@/store/queuesSlice";
import OverviewPage from "@/app/admin/overview/page";
import { StatCard } from "@/components/admin/StatCard";
import { useAdminApi } from "@/hooks/useAdminApi";
import type { AdminOverview } from "@/types/admin";

jest.mock("@/hooks/useAcknowledgeQueueFailuresOnMount", () => ({
  useAcknowledgeQueueFailuresOnMount: jest.fn(),
}));

const baseOverview: AdminOverview = {
  total_projects: 7,
  total_memories: 123,
  memories_last_24h: 9,
  write_queue_queued: 2,
  write_queue_processing: 1,
  write_queue_done: 0,
  write_queue_skipped: 0,
  write_queue_failed: 0,
  governance_queue_queued: 0,
  governance_queue_processing: 0,
  governance_queue_failed: 0,
};

function renderPage(
  overview: AdminOverview | null,
  queues?: {
    failedWriteJobIds?: string[];
    failedGovernanceJobIds?: string[];
  },
) {
  const store = configureStore({
    reducer: { admin: adminReducer, queues: queuesReducer },
  });
  if (overview) store.dispatch(setAdminOverview(overview));
  if (queues?.failedWriteJobIds || queues?.failedGovernanceJobIds) {
    store.dispatch(
      setFailedJobIds({
        write: queues.failedWriteJobIds ?? [],
        governance: queues.failedGovernanceJobIds ?? [],
      }),
    );
  }
  return render(
    <Provider store={store}>
      <OverviewPage />
    </Provider>,
  );
}

describe("OverviewPage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("exibe skeleton (sem métricas) quando overview é null", () => {
    renderPage(null);
    expect(screen.getByText("Visão Geral")).toBeInTheDocument();
    expect(screen.queryByText("Total de Projetos")).not.toBeInTheDocument();
  });

  it("exibe o valor de Total de Projetos quando carregado", () => {
    renderPage(baseOverview);
    expect(screen.getByText("Total de Projetos")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("exibe Total de Memórias correto", () => {
    renderPage(baseOverview);
    expect(screen.getByText("123")).toBeInTheDocument();
  });

  it("card da Fila de Escrita não tem alerta quando write_queue_failed === 0", () => {
    renderPage(baseOverview);
    const card = screen.getByText("Fila de Escrita").closest("[data-alert]");
    expect(card).toHaveAttribute("data-alert", "false");
  });

  it("card da Fila de Escrita tem alerta quando há falha não reconhecida", () => {
    renderPage(
      { ...baseOverview, write_queue_failed: 3 },
      { failedWriteJobIds: ["a", "b", "c"] },
    );
    const card = screen.getByText("Fila de Escrita").closest("[data-alert]");
    expect(card).toHaveAttribute("data-alert", "true");
  });

  it("card da Fila de Governança não tem alerta quando falhas foram reconhecidas", () => {
    window.localStorage.setItem(
      "mem0-admin-queue-ui-prefs-v1",
      JSON.stringify({
        acknowledgedFailedIds: ["governance:job-1"],
        hideCompleted: { write: false, governance: false },
      }),
    );
    renderPage(
      { ...baseOverview, governance_queue_failed: 1 },
      { failedGovernanceJobIds: ["job-1"] },
    );
    const card = screen.getByText("Fila de Governança").closest("[data-alert]");
    expect(card).toHaveAttribute("data-alert", "false");
    expect(screen.queryByText(/com falha/)).not.toBeInTheDocument();
  });

  it("chama useAdminApi na montagem", () => {
    renderPage(baseOverview);
    expect(useAdminApi).toHaveBeenCalled();
  });
});

describe("StatCard", () => {
  it("renderiza title e value passados como props", () => {
    render(<StatCard title="Meu Card" value={42} />);
    expect(screen.getByText("Meu Card")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
