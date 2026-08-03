import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import axios from "axios";

jest.mock("axios");
jest.mock("@/hooks/useApiSessionReady", () => ({
  useApiSessionReady: () => true,
}));
jest.mock("@/lib/api-url", () => ({
  getApiUrl: () => "/api-proxy",
}));

import KanbanBoardPage from "@/app/docs/boards/[boardId]/page";

const mockedAxios = axios as jest.Mocked<typeof axios>;

describe("KanbanBoardPage deep-link", () => {
  beforeEach(() => {
    mockedAxios.get.mockReset();
    mockedAxios.isAxiosError = jest.requireActual("axios").isAxiosError;
  });

  it("carrega embed do quadro via kanban-boards/:id", async () => {
    mockedAxios.get.mockResolvedValue({
      data: {
        board_id: "1833672064557385241",
        embed_url: "/planka/boards/1833672064557385241",
        access_token: "a.b.c",
      },
    });

    render(
      <KanbanBoardPage
        params={Promise.resolve({ boardId: "1833672064557385241" })}
      />,
    );

    await waitFor(() => {
      expect(mockedAxios.get).toHaveBeenCalledWith(
        "/api-proxy/api/v1/specs/kanban-boards/1833672064557385241",
      );
    });

    const iframe = (await screen.findByTestId(
      "kanban-board-canvas",
    )) as HTMLIFrameElement;
    expect(iframe.src).toContain("/planka/boards/1833672064557385241");
    expect(iframe.src).toContain("mem0_token=a.b.c");
    expect(iframe.src).toContain("embed=1");
  });
});
