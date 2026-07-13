/**
 * task_07 (feature auth Google): AuthBridge sincroniza sessão → axios/Redux.
 */
import React from "react";
import { render, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

let mockSession: any = null;
const mockSignOut = jest.fn();
jest.mock("next-auth/react", () => ({
  useSession: () => ({ data: mockSession, status: mockSession ? "authenticated" : "unauthenticated" }),
  signOut: (...args: unknown[]) => mockSignOut(...args),
}));

import { AuthBridge } from "@/components/AuthBridge";
import { getApiAccessToken, setApiAccessToken } from "@/lib/api-client";
import { store } from "@/store/store";

describe("AuthBridge", () => {
  beforeEach(() => {
    mockedAxios.get.mockReset();
    mockSignOut.mockReset();
    setApiAccessToken(null);
    mockSession = null;
    store.dispatch({ type: "profile/clearPersonProfile" });
  });

  it("com sessão: registra o Bearer e popula o perfil via /auth/me", async () => {
    mockSession = { apiAccessToken: "jwt-abc", user: { name: "João" } };
    mockedAxios.get.mockResolvedValue({
      data: {
        user: {
          email: "joao@sysmo.com.br",
          display_name: "João Carlos",
          avatar_url: "https://a/b.png",
        },
        machine: { hostname: "DESKTOP-01" },
        group: "Equipe Fiscal",
      },
    });

    render(
      <Provider store={store}>
        <AuthBridge />
      </Provider>,
    );

    await waitFor(() => {
      expect(getApiAccessToken()).toBe("jwt-abc");
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/me"),
      );
      expect(store.getState().profile.apiSessionStatus).toBe("valid");
      expect(store.getState().profile.person).toEqual({
        email: "joao@sysmo.com.br",
        displayName: "João Carlos",
        avatarUrl: "https://a/b.png",
        machineHostname: "DESKTOP-01",
        group: "Equipe Fiscal",
      });
    });
  });

  it("sem sessão: limpa o Bearer e o perfil", async () => {
    setApiAccessToken("residuo");
    mockSession = null;

    render(
      <Provider store={store}>
        <AuthBridge />
      </Provider>,
    );

    await waitFor(() => {
      expect(getApiAccessToken()).toBeNull();
      expect(store.getState().profile.person).toBeNull();
      expect(store.getState().profile.apiSessionStatus).toBe("idle");
      expect(mockedAxios.get).not.toHaveBeenCalled();
    });
  });

  it("JWT inválido em /auth/me: encerra sessão e redireciona ao login", async () => {
    mockSession = { apiAccessToken: "jwt-expirado" };
    mockedAxios.get.mockRejectedValue({
      isAxiosError: true,
      response: { status: 401 },
    });
    mockedAxios.isAxiosError = jest.fn().mockReturnValue(true);

    render(
      <Provider store={store}>
        <AuthBridge />
      </Provider>,
    );

    await waitFor(() => {
      expect(store.getState().profile.apiSessionStatus).toBe("invalid");
      expect(mockSignOut).toHaveBeenCalledWith({
        callbackUrl: "/login?error=SessionExpired",
      });
    });
  });
});
