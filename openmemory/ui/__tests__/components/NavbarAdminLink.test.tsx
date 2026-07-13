import React from "react";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";

jest.mock("axios");
jest.mock("next/navigation", () => ({
  usePathname: () => "/",
}));
jest.mock("@/app/memories/components/CreateMemoryDialog", () => ({
  CreateMemoryDialog: () => null,
}));

import { store } from "@/store/store";
import { AppSidebar } from "@/components/layout/AppSidebar";

describe("AppSidebar", () => {
  it("contém o link 'Admin' apontando para /admin", () => {
    render(
      <Provider store={store}>
        <AppSidebar open isMobile={false} onClose={jest.fn()} onNavigate={jest.fn()} />
      </Provider>,
    );
    const adminLink = screen.getByRole("link", { name: /admin/i });
    expect(adminLink).toBeInTheDocument();
    expect(adminLink).toHaveAttribute("href", "/admin");
  });

  it("mantém os links de navegação (Painel, Memórias, Projetos, Configurações)", () => {
    render(
      <Provider store={store}>
        <AppSidebar open isMobile={false} onClose={jest.fn()} onNavigate={jest.fn()} />
      </Provider>,
    );
    expect(screen.getByText("Painel")).toBeInTheDocument();
    expect(screen.getByText("Memórias")).toBeInTheDocument();
    expect(screen.getByText("Projetos")).toBeInTheDocument();
    expect(screen.getByText("Configurações")).toBeInTheDocument();
  });
});
