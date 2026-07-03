/**
 * Tela de login via Google Device Flow (ADR-007).
 */
import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

jest.mock("axios");
import axios from "axios";
const mockedAxios = axios as jest.Mocked<typeof axios>;

const mockSignIn = jest.fn().mockResolvedValue(undefined);
jest.mock("next-auth/react", () => ({
  signIn: (...args: any[]) => mockSignIn(...args),
}));

const mockPush = jest.fn();
let mockErrorParam: string | null = null;
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, refresh: jest.fn() }),
  useSearchParams: () => ({
    get: (key: string) => (key === "error" ? mockErrorParam : null),
  }),
}));

import LoginPage from "@/app/login/page";

const DEVICE = {
  device_code: "dev-123",
  user_code: "ABCD-EFGH",
  verification_url: "https://www.google.com/device",
  interval: 5,
};

async function startFlow() {
  fireEvent.click(screen.getByRole("button", { name: /entrar com código/i }));
  await waitFor(() => screen.getByTestId("user-code"));
}

describe("LoginPage (redirect — fluxo primário)", () => {
  beforeEach(() => {
    mockSignIn.mockClear();
    mockErrorParam = null;
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

  it("erro Configuration orienta a usar o código", () => {
    mockErrorParam = "Configuration";
    render(<LoginPage />);
    expect(screen.getByRole("alert").textContent).toMatch(/entrar com código/i);
  });
});

describe("LoginPage (device flow — alternativa)", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockedAxios.post.mockReset();
    mockSignIn.mockClear();
    mockPush.mockReset();
    mockErrorParam = null;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("iniciar login exibe o código e a URL do Google", async () => {
    mockedAxios.post.mockResolvedValueOnce({ data: DEVICE });
    render(<LoginPage />);
    await startFlow();

    expect(mockedAxios.post).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/auth/google/device/start"),
    );
    expect(screen.getByTestId("user-code").textContent).toBe("ABCD-EFGH");
    expect(screen.getByRole("link").getAttribute("href")).toBe(
      "https://www.google.com/device",
    );
  });

  it("polling conclui o login: signIn(device) e redirect para onboarding", async () => {
    mockedAxios.post
      .mockResolvedValueOnce({ data: DEVICE }) // start
      .mockResolvedValueOnce({ data: { status: "pending" } }) // poll 1
      .mockResolvedValueOnce({
        data: { status: "ok", access_token: "jwt-api", first_login: true },
      }); // poll 2
    render(<LoginPage />);
    await startFlow();

    await act(async () => {
      jest.advanceTimersByTime(5000); // poll 1 -> pending
    });
    await act(async () => {
      jest.advanceTimersByTime(5000); // poll 2 -> ok
    });

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith("device", {
        apiToken: "jwt-api",
        redirect: false,
      });
      expect(mockPush).toHaveBeenCalledWith("/onboarding");
    });
  });

  it("usuário já vinculado vai para o painel", async () => {
    mockedAxios.post
      .mockResolvedValueOnce({ data: DEVICE })
      .mockResolvedValueOnce({
        data: { status: "ok", access_token: "jwt-api", first_login: false },
      });
    render(<LoginPage />);
    await startFlow();

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/");
    });
  });

  it("403 (conta fora do domínio corporativo) mostra mensagem e para o polling", async () => {
    mockedAxios.post
      .mockResolvedValueOnce({ data: DEVICE })
      .mockRejectedValueOnce({ response: { status: 403 } });
    render(<LoginPage />);
    await startFlow();

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/domínio da empresa/i);
    });
    expect(screen.queryByTestId("user-code")).toBeNull();
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it("código expirado (410) orienta a recomeçar", async () => {
    mockedAxios.post
      .mockResolvedValueOnce({ data: DEVICE })
      .mockRejectedValueOnce({ response: { status: 410 } });
    render(<LoginPage />);
    await startFlow();

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/expirou/i);
    });
  });

  it("servidor sem login configurado (503) mostra orientação", async () => {
    mockedAxios.post.mockRejectedValueOnce({ response: { status: 503 } });
    render(<LoginPage />);
    fireEvent.click(screen.getByRole("button", { name: /entrar com código/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert").textContent).toMatch(/não configurado/i);
    });
  });

  it("cancelar volta aos botões iniciais e para o polling", async () => {
    mockedAxios.post.mockResolvedValueOnce({ data: DEVICE });
    render(<LoginPage />);
    await startFlow();

    fireEvent.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(screen.getByRole("button", { name: /^entrar com google$/i })).toBeInTheDocument();

    const callsBefore = mockedAxios.post.mock.calls.length;
    await act(async () => {
      jest.advanceTimersByTime(15000);
    });
    expect(mockedAxios.post.mock.calls.length).toBe(callsBefore);
  });
});
