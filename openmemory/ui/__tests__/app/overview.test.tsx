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
import queuesReducer from "@/store/queuesSlice";
import OverviewPage from "@/app/admin/overview/page";
import { StatCard } from "@/components/admin/StatCard";
import { useAdminApi } from "@/hooks/useAdminApi";
import type { AdminOverview } from "@/types/admin";

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

function renderPage(overview: AdminOverview | null) {
  const store = configureStore({
    reducer: { admin: adminReducer, queues: queuesReducer },
  });
  if (overview) store.dispatch(setAdminOverview(overview));
  return render(
    <Provider store={store}>
      <OverviewPage />
    </Provider>,
  );
}

describe("OverviewPage", () => {
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

  it("card da Write Queue não tem alerta quando write_queue_failed === 0", () => {
    renderPage(baseOverview);
    const card = screen.getByText("Write Queue").closest("[data-alert]");
    expect(card).toHaveAttribute("data-alert", "false");
  });

  it("card da Write Queue tem alerta quando write_queue_failed > 0", () => {
    renderPage({ ...baseOverview, write_queue_failed: 3 });
    const card = screen.getByText("Write Queue").closest("[data-alert]");
    expect(card).toHaveAttribute("data-alert", "true");
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
