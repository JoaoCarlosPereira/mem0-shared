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

jest.mock("@/hooks/useAcknowledgeQueueFailuresOnMount", () => ({
  useAcknowledgeQueueFailuresOnMount: jest.fn(),
}));

jest.mock("@/components/dashboard/Install", () => ({
  Install: () => <div data-testid="install" />,
}));

jest.mock("@/app/memories/components/MemoryFilters", () => ({
  MemoryFilters: () => <div data-testid="filters" />,
}));

jest.mock("@/app/memories/components/MemoriesSection", () => ({
  MemoriesSection: () => <div data-testid="memories" />,
}));

import adminReducer, { setAdminOverview } from "@/store/adminSlice";
import queuesReducer from "@/store/queuesSlice";
import DashboardPage from "@/app/page";
import type { AdminOverview } from "@/types/admin";

const baseOverview: AdminOverview = {
  total_projects: 1,
  total_memories: 19,
  memories_last_24h: 10,
  write_queue_queued: 0,
  write_queue_processing: 0,
  write_queue_done: 0,
  write_queue_skipped: 0,
  write_queue_failed: 0,
  governance_queue_queued: 0,
  governance_queue_processing: 0,
  governance_queue_failed: 0,
};

function renderHome(overview: AdminOverview | null) {
  const store = configureStore({
    reducer: { admin: adminReducer, queues: queuesReducer },
  });
  if (overview) store.dispatch(setAdminOverview(overview));
  return render(
    <Provider store={store}>
      <DashboardPage />
    </Provider>,
  );
}

describe("DashboardPage metrics", () => {
  it("substitui KPIs antigos pelos cards da visão geral", () => {
    renderHome(baseOverview);
    expect(screen.getByText("Total de Projetos")).toBeInTheDocument();
    expect(screen.getByText("Total de Memórias")).toBeInTheDocument();
    expect(screen.getByText("Memórias (últimas 24h)")).toBeInTheDocument();
    expect(screen.getByText("Fila de Escrita")).toBeInTheDocument();
    expect(screen.getByText("Fila de Governança")).toBeInTheDocument();
    expect(screen.getByText("19")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.queryByText("Projetos Conectados")).not.toBeInTheDocument();
  });
});
