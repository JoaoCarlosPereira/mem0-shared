import React from "react";
import { render, screen } from "@testing-library/react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";

const mockUsePathname = jest.fn();
jest.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
  redirect: jest.fn(),
}));

import adminReducer from "@/store/adminSlice";
import queuesReducer, { setWriteQueue } from "@/store/queuesSlice";
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
});

describe("AdminSidebar", () => {
  it("renderiza os 5 itens de menu", () => {
    renderSidebar();
    ["Overview", "Filas", "Projetos", "Governança", "Audit Log"].forEach(
      (label) => {
        expect(screen.getByText(label)).toBeInTheDocument();
      },
    );
  });

  it("marca Overview como ativo quando pathname é /admin/overview", () => {
    renderSidebar();
    const overview = screen.getByText("Overview").closest("a");
    expect(overview).toHaveAttribute("aria-current", "page");
  });

  it("não renderiza badge quando failedCount é 0", () => {
    renderSidebar();
    expect(screen.queryByLabelText(/jobs com falha/i)).not.toBeInTheDocument();
  });

  it("exibe badge com o número correto quando failedCount é 3", () => {
    const store = makeStore();
    store.dispatch(
      setWriteQueue({
        items: [],
        total: 0,
        page: 1,
        pages: 0,
        failed_count: 3,
      }),
    );
    renderSidebar(store);
    const badge = screen.getByLabelText(/jobs com falha/i);
    expect(badge).toHaveTextContent("3");
  });
});

describe("/admin redirect", () => {
  it("redireciona para /admin/overview", () => {
    AdminIndexPage();
    expect(redirect).toHaveBeenCalledWith("/admin/overview");
  });
});
