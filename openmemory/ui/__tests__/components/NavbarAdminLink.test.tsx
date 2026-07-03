import React from "react";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";

jest.mock("axios");
jest.mock("next/navigation", () => ({
  usePathname: () => "/",
}));
// Stub do dialog de criação para isolar o teste do link "Admin".
jest.mock("@/app/memories/components/CreateMemoryDialog", () => ({
  CreateMemoryDialog: () => null,
}));
// Navbar renderiza <UserMenu/> (feature auth Google); sem SessionProvider no
// teste, o hook é mockado como não autenticado (menu oculto).
jest.mock("next-auth/react", () => ({
  useSession: () => ({ data: null, status: "unauthenticated" }),
  signOut: jest.fn(),
}));

import { store } from "@/store/store";
import { Navbar } from "@/components/Navbar";

describe("Navbar", () => {
  it("contém o link 'Admin' apontando para /admin", () => {
    render(
      <Provider store={store}>
        <Navbar />
      </Provider>,
    );
    const adminLink = screen.getByRole("link", { name: /admin/i });
    expect(adminLink).toBeInTheDocument();
    expect(adminLink).toHaveAttribute("href", "/admin");
  });

  it("mantém os links existentes (Painel, Memórias, Projetos, Configurações)", () => {
    render(
      <Provider store={store}>
        <Navbar />
      </Provider>,
    );
    expect(screen.getByText("Painel")).toBeInTheDocument();
    expect(screen.getByText("Memórias")).toBeInTheDocument();
    expect(screen.getByText("Projetos")).toBeInTheDocument();
    expect(screen.getByText("Configurações")).toBeInTheDocument();
  });
});
