/**
 * Tela de instalação do dashboard: token imutável criado automaticamente e
 * embutido nos comandos (ADR-008). Aguarda sessão autenticada no 2º login.
 * Grupo da conta é pré-carregado quando já vinculado (GET /auth/me → profileSlice).
 */
import React from "react";
import { configureStore } from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import { render, screen, waitFor } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

let mockSession: any = null;
let mockStatus = "loading";
jest.mock("next-auth/react", () => ({
  useSession: () => ({ data: mockSession, status: mockStatus }),
}));

jest.mock("@/lib/api-url", () => {
  const actual = jest.requireActual<typeof import("@/lib/api-url")>("@/lib/api-url");
  return {
    ...actual,
    fetchMcpBaseUrl: jest.fn().mockResolvedValue("http://192.168.3.213:8765"),
  };
});

import profileReducer from "@/store/profileSlice";
import { Install } from "@/components/dashboard/Install";

const TOKEN = {
  token: "omtk_valorfixo123",
  prefix: "omtk_valo",
  created_at: "2026-07-03T10:00:00",
  last_used_at: null,
};

function makeStore(profileGroup: string | null = null) {
  return configureStore({
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
}

function renderInstall(profileGroup: string | null = null) {
  const store = makeStore(profileGroup);
  return {
    store,
    ...render(
      <Provider store={store}>
        <Install />
      </Provider>,
    ),
  };
}

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
    renderInstall();

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
    const store = makeStore();
    const { rerender } = render(
      <Provider store={store}>
        <Install />
      </Provider>,
    );

    expect(mockedAxios.post).not.toHaveBeenCalled();

    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-novo-login" };
    rerender(
      <Provider store={store}>
        <Install />
      </Provider>,
    );

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
    const { container } = renderInstall();
    await waitFor(() => screen.getByTestId("token-banner"));

    // Comandos da aba padrão (Claude) carregam o token real e o IP da LAN.
    const commands = Array.from(container.querySelectorAll("pre code"))
      .map((el) => el.textContent ?? "")
      .join("\n");
    expect(commands).toContain("token=omtk_valorfixo123");
    expect(commands).toContain("http://192.168.3.213:8765");
    expect(commands).not.toContain("SEU_TOKEN");
  });

  it("sem sessão: comandos usam placeholder e a página não quebra", async () => {
    mockStatus = "unauthenticated";
    mockSession = null;
    const { container } = renderInstall();

    await waitFor(() => {
      expect(mockedAxios.post).not.toHaveBeenCalled();
    });
    expect(screen.queryByTestId("token-banner")).toBeNull();
    const commands = Array.from(container.querySelectorAll("pre code"))
      .map((el) => el.textContent ?? "")
      .join("\n");
    expect(commands).toContain("token=SEU_TOKEN");
  });

  it("pré-carrega o grupo vinculado à conta e bloqueia edição", async () => {
    mockStatus = "authenticated";
    mockSession = { apiAccessToken: "jwt-sessao" };
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
