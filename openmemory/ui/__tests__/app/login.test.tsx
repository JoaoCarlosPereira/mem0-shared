/**
 * Tela de login via Google OAuth redirect (ADR-002).
 */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

const mockSignIn = jest.fn().mockResolvedValue(undefined);
jest.mock("next-auth/react", () => ({
  signIn: (...args: any[]) => mockSignIn(...args),
}));

let mockErrorParam: string | null = null;
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), refresh: jest.fn() }),
  useSearchParams: () => ({
    get: (key: string) => (key === "error" ? mockErrorParam : null),
  }),
}));

import LoginPage from "@/app/login/page";

describe("LoginPage", () => {
  beforeEach(() => {
    mockSignIn.mockClear();
    mockErrorParam = null;
  });

  it("exibe apenas o botão de login com Google", () => {
    render(<LoginPage />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(1);
    expect(buttons[0].textContent).toMatch(/^entrar com google$/i);
  });

  it("botão principal dispara o signIn com redirect", () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /^entrar com google$/i }));
    expect(mockSignIn).toHaveBeenCalledWith("google", { redirectTo: "/" });
  });

  it("erro AccessDenied do redirect mostra mensagem de domínio", () => {
    mockErrorParam = "AccessDenied";
    render(<LoginPage />);
    expect(screen.getByRole("alert").textContent).toMatch(/domínio da empresa/i);
  });

  it("erro Configuration mostra mensagem de indisponibilidade", () => {
    mockErrorParam = "Configuration";
    render(<LoginPage />);
    expect(screen.getByRole("alert").textContent).toMatch(/indisponível/i);
  });
});
