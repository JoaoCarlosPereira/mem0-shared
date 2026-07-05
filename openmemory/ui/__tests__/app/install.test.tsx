/**
 * Página de consulta do token de agente (ADR-008: imutável, sempre visível).
 */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

const mockToastApi = { toast: jest.fn() };
jest.mock("@/hooks/use-toast", () => ({
  useToast: () => mockToastApi,
}));

let mockSession: any = null;
let mockStatus = "loading";
jest.mock("next-auth/react", () => ({
  useSession: () => ({ data: mockSession, status: mockStatus }),
}));

import AgentTokenPage from "@/app/settings/install/page";

const TOKEN = {
  token: "omtk_valorfixo123",
  prefix: "omtk_valo",
  created_at: "2026-07-03T10:00:00",
  last_used_at: null,
};

describe("AgentTokenPage", () => {
  beforeEach(() => {
    mockedAxios.post.mockReset();
    mockSession = null;
    mockStatus = "loading";
    Object.assign(navigator, {
      clipboard: { writeText: jest.fn().mockResolvedValue(undefined) },
    });
  });

  it("get-or-create exibe o token permanentemente", async () => {
    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-sessao" };
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    render(<AgentTokenPage />);

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/agent-token"),
        undefined,
        expect.objectContaining({
          headers: { Authorization: "Bearer jwt-sessao" },
        }),
      );
      expect(screen.getByTestId("raw-token").textContent).toBe(
        "omtk_valorfixo123",
      );
    });
  });

  it("copiar coloca o token no clipboard", async () => {
    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-sessao" };
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    render(<AgentTokenPage />);
    await waitFor(() => screen.getByTestId("raw-token"));

    fireEvent.click(screen.getByRole("button", { name: /copiar token/i }));
    await waitFor(() => {
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "omtk_valorfixo123",
      );
    });
  });

  it("falha de carregamento mostra erro", async () => {
    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-sessao" };
    mockedAxios.post.mockRejectedValue({ response: { status: 500 } });
    render(<AgentTokenPage />);
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/não foi possível/i);
    });
  });
});
