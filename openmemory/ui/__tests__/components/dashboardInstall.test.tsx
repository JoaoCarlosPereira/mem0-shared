/**
 * Tela de instalação do dashboard: token imutável criado automaticamente e
 * embutido nos comandos (ADR-008). Grupo da conta é pré-carregado quando já
 * vinculado (GET /auth/me → profileSlice).
 */
import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { render, screen, waitFor } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

import profileReducer from "@/store/profileSlice";
import { Install } from "@/components/dashboard/Install";

const TOKEN = {
  token: "omtk_valorfixo123",
  prefix: "omtk_valo",
  created_at: "2026-07-03T10:00:00",
  last_used_at: null,
};

function renderInstall(profileGroup: string | null = null) {
  const store = configureStore({
    reducer: { profile: profileReducer },
    preloadedState: profileGroup
      ? {
          profile: {
            userId: "user",
            person: {
              email: "joao@sysmo.com.br",
              displayName: "João",
              avatarUrl: null,
              machineHostname: "DESKTOP-01",
              group: profileGroup,
            },
            totalMemories: 0,
            totalApps: 0,
            status: "idle",
            error: null,
            apps: [],
          },
        }
      : undefined,
  });

  return render(
    <Provider store={store}>
      <Install />
    </Provider>,
  );
}

describe("Install (dashboard)", () => {
  beforeEach(() => {
    mockedAxios.post.mockReset();
  });

  it("cria o token automaticamente (get-or-create) na primeira visita", async () => {
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    renderInstall();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/agent-token"),
      );
      expect(screen.getByTestId("raw-token").textContent).toBe(
        "omtk_valorfixo123",
      );
    });
  });

  it("exibe o token permanentemente e embutido nos comandos de instalação", async () => {
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    const { container } = renderInstall();
    await waitFor(() => screen.getByTestId("token-banner"));

    // Comandos da aba padrão (Claude) carregam o token real na URL MCP.
    const commands = Array.from(container.querySelectorAll("pre code"))
      .map((el) => el.textContent ?? "")
      .join("\n");
    expect(commands).toContain("token=omtk_valorfixo123");
    expect(commands).not.toContain("SEU_TOKEN");
  });

  it("sem sessão/erro: comandos usam placeholder e a página não quebra", async () => {
    mockedAxios.post.mockRejectedValue({ response: { status: 401 } });
    const { container } = renderInstall();

    await waitFor(() => {
      expect(mockedAxios.post).toHaveBeenCalled();
    });
    expect(screen.queryByTestId("token-banner")).toBeNull();
    const commands = Array.from(container.querySelectorAll("pre code"))
      .map((el) => el.textContent ?? "")
      .join("\n");
    expect(commands).toContain("token=SEU_TOKEN");
  });

  it("pré-carrega o grupo vinculado à conta e bloqueia edição", async () => {
    mockedAxios.post.mockResolvedValue({ data: TOKEN });
    const { container } = renderInstall("Equipe Fiscal");
    await waitFor(() => screen.getByTestId("token-banner"));

    const input = screen.getByLabelText(/grupo \(equipe\)/i) as HTMLInputElement;
    expect(input.value).toBe("Equipe Fiscal");
    expect(input).toHaveAttribute("readonly");

    const commands = Array.from(container.querySelectorAll("pre code"))
      .map((el) => el.textContent ?? "")
      .join("\n");
    expect(commands).toContain("group=Equipe%20Fiscal");
  });
});
