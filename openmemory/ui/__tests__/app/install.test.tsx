/**
 * Página de consulta do token de agente (ADR-008: imutável, sempre visível).
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const mockToastApi = { toast: jest.fn() };
jest.mock("@/hooks/use-toast", () => ({
  useToast: () => mockToastApi,
}));

jest.mock("@/hooks/useImmutableAgentToken", () => ({
  useImmutableAgentToken: jest.fn(),
}));

import AgentTokenPage from "@/app/admin/settings/install/page";
import { useImmutableAgentToken } from "@/hooks/useImmutableAgentToken";

const TOKEN = {
  token: "omtk_valorfixo123",
  prefix: "omtk_valo",
  created_at: "2026-07-03T10:00:00",
  last_used_at: null,
};

const mockedHook = useImmutableAgentToken as jest.MockedFunction<
  typeof useImmutableAgentToken
>;

describe("AgentTokenPage", () => {
  beforeEach(() => {
    mockToastApi.toast.mockClear();
    Object.assign(navigator, {
      clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
  });

  it("get-or-create exibe o token permanentemente", async () => {
    mockedHook.mockReturnValue({
      rawToken: TOKEN.token,
      tokenInfo: TOKEN,
      error: false,
      loading: false,
    });
    render(<AgentTokenPage />);
    expect(screen.getByTestId("raw-token").textContent).toBe("omtk_valorfixo123");
  });

  it("copiar coloca o token no clipboard", async () => {
    mockedHook.mockReturnValue({
      rawToken: TOKEN.token,
      tokenInfo: TOKEN,
      error: false,
      loading: false,
    });
    render(<AgentTokenPage />);
    fireEvent.click(screen.getByRole("button", { name: /copiar/i }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "omtk_valorfixo123",
      );
    });
  });

  it("falha de carregamento mostra erro", async () => {
    mockedHook.mockReturnValue({
      rawToken: null,
      tokenInfo: null,
      error: true,
      loading: false,
    });
    render(<AgentTokenPage />);
    expect(screen.getByRole("alert").textContent).toMatch(/não foi possível/i);
  });
});
