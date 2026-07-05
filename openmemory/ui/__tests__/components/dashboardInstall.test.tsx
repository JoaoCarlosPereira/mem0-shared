/**
 * Token imutável: aguarda sessão autenticada antes do get-or-create (2º login).
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

let mockSession: any = null;
let mockStatus = "loading";
jest.mock("next-auth/react", () => ({
  useSession: () => ({ data: mockSession, status: mockStatus }),
}));

import { Install } from "@/components/dashboard/Install";

const TOKEN = {
  token: "omtk_valorfixo123",
  prefix: "omtk_valo",
  created_at: "2026-07-03T10:00:00",
  last_used_at: null,
};

describe("Install (dashboard)", () => {
  beforeEach(() => {
    mockedAxios.post.mockReset();
    mockSession = null;
    mockStatus = "loading";
  });

  it("cria o token automaticamente (get-or-create) na primeira visita", async () => {
    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-sessao" };
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    render(<Install />);

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

  it("2º login: aguarda sessão e carrega o token existente", async () => {
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    const { rerender } = render(<Install />);

    expect(mockedAxios.post).not.toHaveBeenCalled();

    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-novo-login" };
    rerender(<Install />);

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/agent-token"),
        undefined,
        expect.objectContaining({
          headers: { Authorization: "Bearer jwt-novo-login" },
        }),
      );
      expect(screen.getByTestId("raw-token").textContent).toBe(
        "omtk_valorfixo123",
      );
    });
  });

  it("exibe o token permanentemente e embutido nos comandos de instalação", async () => {
    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-sessao" };
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    const { container } = render(<Install />);
    await waitFor(() => screen.getByTestId("token-banner"));

    const commands = Array.from(container.querySelectorAll("pre code"))
      .map((el) => el.textContent ?? "")
      .join("\n");
    expect(commands).toContain("token=omtk_valorfixo123");
    expect(commands).not.toContain("SEU_TOKEN");
  });

  it("sem sessão: comandos usam placeholder e a página não quebra", async () => {
    mockStatus = "unauthenticated";
    mockSession = null;
    const { container } = render(<Install />);

    await waitFor(() => {
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });
    expect(screen.queryByTestId("token-banner")).toBeNull();
    const commands = Array.from(container.querySelectorAll("pre code"))
      .map((el) => el.textContent ?? "")
      .join("\n");
    expect(commands).toContain("token=SEU_TOKEN");
  });
});
