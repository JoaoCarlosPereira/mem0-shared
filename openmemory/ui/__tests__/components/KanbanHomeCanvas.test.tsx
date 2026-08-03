import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";

jest.mock("axios");
jest.mock("@/hooks/useApiSessionReady", () => ({
  useApiSessionReady: jest.fn(),
}));
jest.mock("@/lib/api-url", () => ({
  getApiUrl: () => "/api-proxy",
}));

import { KanbanHomeCanvas } from "@/components/docs/KanbanHomeCanvas";
import { useApiSessionReady } from "@/hooks/useApiSessionReady";

const mockedAxios = axios as jest.Mocked<typeof axios>;
const mockedReady = useApiSessionReady as jest.MockedFunction<typeof useApiSessionReady>;

describe("KanbanHomeCanvas identity bootstrap", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedAxios.isAxiosError = jest.requireActual("axios").isAxiosError;
  });

  it("aguarda apiSessionReady antes de chamar kanban-home", () => {
    mockedReady.mockReturnValue(false);
    render(<KanbanHomeCanvas />);
    expect(screen.getByTestId("kanban-home-loading")).toBeInTheDocument();
    expect(mockedAxios.get).not.toHaveBeenCalled();
  });

  it("usa axios (Bearer AuthBridge) e monta iframe com mem0_token", async () => {
    mockedReady.mockReturnValue(true);
    mockedAxios.get.mockResolvedValue({
      data: {
        embed_url: "/planka/",
        access_token: "jwt-person-token",
      },
    });

    render(<KanbanHomeCanvas />);

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        "/api-proxy/api/v1/specs/kanban-home",
      );
    });
    await waitFor(() => {
      const iframe = screen.getByTestId("kanban-home-canvas") as HTMLIFrameElement;
      expect(iframe.src).toContain("mem0_token=jwt-person-token");
      expect(iframe.src).toContain("embed=1");
    });
  });

  it("mostra erro e permite retry quando kanban-home falha", async () => {
    mockedReady.mockReturnValue(true);
    mockedAxios.get
      .mockRejectedValueOnce({
        isAxiosError: true,
        message: "Network Error",
        response: { data: { detail: "AUTH_JWT_SECRET necessário" } },
      })
      .mockResolvedValueOnce({
        data: {
          embed_url: "/planka/",
          access_token: "jwt-retry-token",
        },
      });

    render(<KanbanHomeCanvas />);

    await waitFor(() => {
      expect(screen.getByTestId("kanban-home-error")).toBeInTheDocument();
      expect(screen.getByRole("alert")).toHaveTextContent(
        "AUTH_JWT_SECRET necessário",
      );
    });

    await waitFor(async () => {
      screen.getByRole("button", { name: /tentar de novo/i }).click();
      expect(await screen.findByTestId("kanban-home-canvas")).toBeInTheDocument();
    });

    const iframe = screen.getByTestId("kanban-home-canvas") as HTMLIFrameElement;
    expect(iframe.src).toContain("mem0_token=jwt-retry-token");
  });
});
