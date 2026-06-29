import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

jest.mock("@/hooks/useQueuesApi", () => ({
  useQueuesApi: jest.fn(() => ({
    fetchWriteQueue: jest.fn(),
    fetchGovernanceJobs: jest.fn(),
    refreshAll: jest.fn(),
    retryFailedWriteJobs: jest.fn(),
  })),
}));
jest.mock("@/hooks/useAdminApi", () => ({
  useAdminApi: jest.fn(() => ({
    fetchAdminOverview: jest.fn(),
    fetchWriteAudit: jest.fn(),
    fetchProjectSizes: jest.fn(),
  })),
}));

import adminReducer from "@/store/adminSlice";
import queuesReducer, { setWriteQueue } from "@/store/queuesSlice";
import QueuesPage from "@/app/admin/queues/page";
import type { WriteQueueJob } from "@/types/admin";

beforeEach(() => {
  mockedAxios.get.mockResolvedValue({
    data: { items: [], total: 0, page: 1, pages: 0, failed_count: 0 },
  });
});

const job: WriteQueueJob = {
  id: "j1",
  project: "proj-a",
  hostname: "host1",
  client_name: "cli",
  text_preview: "olá mundo",
  status: "failed",
  error: "boom error",
  attempts: 2,
  created_at: "2026-01-01T10:00:00Z",
};

function renderPage() {
  const store = configureStore({
    reducer: { admin: adminReducer, queues: queuesReducer },
  });
  store.dispatch(
    setWriteQueue({
      items: [job],
      total: 1,
      page: 1,
      pages: 2,
      failed_count: 1,
    }),
  );
  const utils = render(
    <Provider store={store}>
      <QueuesPage />
    </Provider>,
  );
  return { store, ...utils };
}

describe("QueuesPage", () => {
  it("aba Write Queue ativa por padrão exibe o job", () => {
    renderPage();
    expect(screen.getByText("olá mundo")).toBeInTheDocument();
  });

  it("erro da write queue é exibido em vermelho", () => {
    renderPage();
    const err = screen.getByText("boom error");
    expect(err).toHaveClass("text-red-400");
  });

  it("clicar em 'Fila de Governança' troca para a aba correta", async () => {
    renderPage();
    await userEvent.click(
      screen.getByRole("tab", { name: "Fila de Governança" }),
    );
    // A aba governance (vazia) mostra a mensagem de vazio
    expect(screen.getAllByText("Nenhum job encontrado").length).toBeGreaterThan(
      0,
    );
  });

  it("filtro de projeto despacha setWriteQueueFilter ao sair do campo", async () => {
    const { store } = renderPage();
    const input = screen.getAllByPlaceholderText("Filtrar por projeto")[0];
    await userEvent.type(input, "proj-x");
    await userEvent.tab();
    expect(store.getState().queues.writeQueueFilter.project).toBe("proj-x");
  });

  it("paginação despacha mudança de página", async () => {
    const { store } = renderPage();
    await userEvent.click(screen.getByText("Próxima página"));
    expect(store.getState().queues.writeQueueFilter.page).toBe(2);
  });
});
