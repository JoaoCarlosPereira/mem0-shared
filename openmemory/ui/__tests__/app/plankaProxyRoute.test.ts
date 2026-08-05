import type { NextRequest } from "next/server";

import { DELETE, GET, POST } from "@/app/planka/[[...path]]/route";

jest.mock("next/server", () => {
  class MockNextResponse {
    body: BodyInit | null;
    headers: Headers;
    status: number;

    constructor(body?: BodyInit | null, init?: ResponseInit) {
      this.body = body ?? null;
      this.headers = new Headers(init?.headers);
      this.status = init?.status ?? 200;
    }

    static json(body: unknown, init?: ResponseInit) {
      const headers = new Headers(init?.headers);
      if (!headers.has("content-type")) {
        headers.set("content-type", "application/json");
      }
      return new MockNextResponse(JSON.stringify(body), { ...init, headers });
    }

    async json() {
      return JSON.parse(await this.text());
    }

    async text() {
      if (typeof this.body === "string") return this.body;
      if (this.body instanceof ArrayBuffer) {
        return Buffer.from(this.body).toString("utf8");
      }
      return "";
    }
  }

  return { NextResponse: MockNextResponse };
});

type RequestOptions = {
  method?: string;
  headers?: HeadersInit;
  body?: string;
};

function makeRequest(url: string, options: RequestOptions = {}): NextRequest {
  const body = options.body ?? "";
  return {
    method: options.method ?? "GET",
    headers: new Headers(options.headers),
    nextUrl: new URL(url),
    arrayBuffer: async () => {
      const buffer = Buffer.from(body);
      return buffer.buffer.slice(
        buffer.byteOffset,
        buffer.byteOffset + buffer.byteLength,
      );
    },
  } as unknown as NextRequest;
}

function routeContext(path?: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("planka route proxy", () => {
  const originalPlankaUrl = process.env.PLANKA_INTERNAL_URL;
  const originalFetch = global.fetch;

  beforeEach(() => {
    const { NextResponse } = jest.requireMock("next/server");
    process.env.PLANKA_INTERNAL_URL = "http://planka:1337";
    global.fetch = jest.fn().mockResolvedValue(
      new NextResponse("<html>board</html>", {
        status: 200,
        headers: { "content-type": "text/html" },
      }),
    );
  });

  afterEach(() => {
    process.env.PLANKA_INTERNAL_URL = originalPlankaUrl;
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it("encaminha a raiz (sem segmentos) para / no sidecar, sem o prefixo /planka", async () => {
    const response = await GET(
      makeRequest("http://openmemory.local/planka"),
      routeContext(undefined),
    );

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [target] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(target).toBe("http://planka:1337/");
  });

  it("encaminha GET com sub-caminho e query string, sem headers hop-by-hop", async () => {
    const response = await GET(
      makeRequest("http://openmemory.local/planka/js/main.js?v=2", {
        headers: {
          cookie: "planka-session=abc",
          connection: "keep-alive",
          "x-client-name": "openmemory-ui",
        },
      }),
      routeContext(["js", "main.js"]),
    );

    expect(response.status).toBe(200);
    const [target, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const headers = init.headers as Headers;
    expect(target).toBe("http://planka:1337/js/main.js?v=2");
    expect(init.method).toBe("GET");
    // Cookie de sessão do PLANKA precisa passar — diferente de /registry-api,
    // aqui não há allowlist/injeção de Bearer, o board usa a própria sessão.
    expect(headers.get("cookie")).toBe("planka-session=abc");
    expect(headers.get("x-client-name")).toBe("openmemory-ui");
    expect(headers.has("connection")).toBe(false);
  });

  it("codifica segmentos de path com caracteres especiais", async () => {
    await GET(
      makeRequest("http://openmemory.local/planka/api/cards/team/card-1"),
      routeContext(["api", "cards", "team/card-1"]),
    );

    const [target] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(target).toBe("http://planka:1337/api/cards/team%2Fcard-1");
  });

  it("encaminha POST com body preservado", async () => {
    const response = await POST(
      makeRequest("http://openmemory.local/planka/api/cards", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: '{"name":"Novo card"}',
      }),
      routeContext(["api", "cards"]),
    );

    expect(response.status).toBe(200);
    const [target, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const forwardedBody = Buffer.from(init.body as ArrayBuffer).toString("utf8");
    expect(target).toBe("http://planka:1337/api/cards");
    expect(init.method).toBe("POST");
    expect(init.redirect).toBe("manual");
    expect(forwardedBody).toBe('{"name":"Novo card"}');
  });

  it("responde 502 em JSON quando o sidecar está indisponível", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("ECONNREFUSED"));

    const response = await DELETE(
      makeRequest("http://openmemory.local/planka/api/cards/1", {
        method: "DELETE",
      }),
      routeContext(["api", "cards", "1"]),
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toMatchObject({
      detail: "PLANKA indisponível",
    });
  });
});
