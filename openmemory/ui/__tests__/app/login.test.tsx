/**
 * Tela de login via Google OAuth redirect (ADR-002).
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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
    (globalThis.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({ google: { id: "google", name: "Google" } }),
    });
  });

  it("exibe apenas o botão de login com Google", async () => {
    render(<LoginPage />);
    const button = await screen.findByRole("button", {
      name: /^entrar com google$/i,
    });
    expect(button).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("botão principal dispara o signIn com redirect", async () => {
    render(<LoginPage />);
    fireEvent.click(
      await screen.findByRole("button", { name: /^entrar com google$/i }),
    );
    expect(mockSignIn).toHaveBeenCalledWith("google", { redirectTo: "/" });
  });

  it("erro AccessDenied do redirect mostra mensagem de domínio", async () => {
    mockErrorParam = "AccessDenied";
    render(<LoginPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/domínio da empresa/i);
  });

  it("erro Configuration mostra mensagem de indisponibilidade", async () => {
    mockErrorParam = "Configuration";
    render(<LoginPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/indisponível/i);
  });
});
