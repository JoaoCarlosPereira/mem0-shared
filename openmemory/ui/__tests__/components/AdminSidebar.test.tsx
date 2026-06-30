import React from "react";
import { render, screen } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

const mockUsePathname = jest.fn();
jest.mock("@/hooks/useQueueFailedAlerts", () => ({
  useQueueFailedAlerts: jest.fn(),
}));
jest.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
  redirect: jest.fn(),
}));

import adminReducer from "@/store/adminSlice";
import queuesReducer, {
  setWriteQueue,
  setFailedJobIds,
  bumpQueueUiPrefs,
} from "@/store/queuesSlice";
import { acknowledgeFailedJobs } from "@/lib/queue-ui-prefs";
import { AdminSidebar } from "@/components/admin/AdminSidebar";
import AdminIndexPage from "@/app/admin/page";
import { redirect } from "next/navigation";

function makeStore() {
  return configureStore({
    reducer: { admin: adminReducer, queues: queuesReducer },
  });
}

function renderSidebar(store = makeStore()) {
  return render(
    <Provider store={store}>
      <AdminSidebar />
    </Provider>,
  );
}

beforeEach(() => {
  mockUsePathname.mockReturnValue("/admin/overview");
  window.localStorage.clear();
});

describe("AdminSidebar", () => {
  it("renderiza os itens de menu, incluindo Grupos", () => {
    renderSidebar();
    [
      "Visão Geral",
      "Filas",
      "Projetos",
      "Grupos",
      "Governança",
      "Log de Auditoria",
    ].forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("marca Visão Geral como ativo quando pathname é /admin/overview", () => {
    renderSidebar();
    const overview = screen.getByText("Visão Geral").closest("a");
    expect(overview).toHaveAttribute("aria-current", "page");
  });

  it("não renderiza badge quando failedCount é 0", () => {
    renderSidebar();
    expect(screen.queryByLabelText(/jobs com falha/i)).not.toBeInTheDocument();
  });

  it("exibe badge com falhas não reconhecidas", () => {
    const store = makeStore();
    store.dispatch(setFailedJobIds({ write: ["f1", "f2", "f3"], governance: [] }));
    store.dispatch(bumpQueueUiPrefs());
    renderSidebar(store);
    const badge = screen.getByLabelText(/jobs com falha/i);
    expect(badge).toHaveTextContent("3");
  });

  it("não exibe badge após falhas serem reconhecidas", () => {
    acknowledgeFailedJobs(["f1", "f2", "f3"], []);
    const store = makeStore();
    store.dispatch(setFailedJobIds({ write: ["f1", "f2", "f3"], governance: [] }));
    store.dispatch(bumpQueueUiPrefs());
    renderSidebar(store);
    expect(screen.queryByLabelText(/jobs com falha/i)).not.toBeInTheDocument();
  });
});

describe("/admin redirect", () => {
  it("redireciona para /admin/overview", () => {
    AdminIndexPage();
    expect(redirect).toHaveBeenCalledWith("/admin/overview");
  });
});
