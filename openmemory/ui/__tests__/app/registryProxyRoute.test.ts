import type { NextRequest } from "next/server";

import { DELETE, GET, POST } from "@/app/registry-api/[...path]/route";

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

function routeContext(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

describe("registry-api route proxy", () => {
  const originalRegistryUrl = process.env.AGENT_REGISTRY_INTERNAL_URL;
  const originalAuthUiRequired = process.env.AUTH_UI_REQUIRED;
  const originalGoogleClientId = process.env.GOOGLE_CLIENT_ID;
  const originalPublicGoogleClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  const originalFetch = global.fetch;

  beforeEach(() => {
    const { NextResponse } = jest.requireMock("next/server");
    process.env.AGENT_REGISTRY_INTERNAL_URL = "http://agentregistry:8080";
    // Default dos testes de allowlist/forward: modo Google (fail-closed sem Bearer).
    process.env.AUTH_UI_REQUIRED = "1";
    delete process.env.GOOGLE_CLIENT_ID;
    delete process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    global.fetch = jest.fn().mockResolvedValue(
      new NextResponse(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
  });

  afterEach(() => {
    process.env.AGENT_REGISTRY_INTERNAL_URL = originalRegistryUrl;
    process.env.AUTH_UI_REQUIRED = originalAuthUiRequired;
    process.env.GOOGLE_CLIENT_ID = originalGoogleClientId;
    process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID = originalPublicGoogleClientId;
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it("com Google auth falha fechado quando Authorization está ausente", async () => {
    const response = await GET(
      makeRequest("http://openmemory.local/registry-api/v0/skills"),
      routeContext(["v0", "skills"]),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      detail: "registry authentication required",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("em UI legado injeta Bearer local e encaminha sem Authorization do browser", async () => {
    process.env.AUTH_UI_REQUIRED = "0";

    const response = await GET(
      makeRequest("http://openmemory.local/registry-api/v0/skills?namespace=all"),
      routeContext(["v0", "skills"]),
    );

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect((init.headers as Headers).get("authorization")).toBe("Bearer local");
  });

  it("nega métodos e caminhos fora da allowlist", async () => {
    const response = await DELETE(
      makeRequest("http://openmemory.local/registry-api/v0/skills/demo", {
        method: "DELETE",
        headers: { authorization: "Bearer local" },
      }),
      routeContext(["v0", "skills", "demo"]),
    );

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({
      detail: "registry endpoint not allowed",
    });
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("encaminha GET permitido com Authorization e sem headers hop-by-hop", async () => {
    const response = await GET(
      makeRequest("http://openmemory.local/registry-api/v0/skills?namespace=all", {
        headers: {
          authorization: "Bearer jwt-session",
          connection: "keep-alive",
          cookie: "next-auth.session-token=secret",
          "x-client-name": "openmemory-ui",
        },
      }),
      routeContext(["v0", "skills"]),
    );

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const [target, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const headers = init.headers as Headers;
    expect(target).toBe("http://agentregistry:8080/v0/skills?namespace=all");
    expect(init.method).toBe("GET");
    expect(headers.get("authorization")).toBe("Bearer jwt-session");
    expect(headers.get("x-client-name")).toBe("openmemory-ui");
    expect(headers.has("connection")).toBe(false);
    expect(headers.has("cookie")).toBe(false);
  });

  it("encaminha POST /v0/apply com body e Authorization omtk", async () => {
    const response = await POST(
      makeRequest("http://openmemory.local/registry-api/v0/apply", {
        method: "POST",
        headers: {
          authorization: "Bearer omtk_token",
          "content-type": "application/yaml",
        },
        body: "kind: Skill\nmetadata:\n  name: demo\n",
      }),
      routeContext(["v0", "apply"]),
    );

    expect(response.status).toBe(200);
    const [target, init] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    const headers = init.headers as Headers;
    const forwardedBody = Buffer.from(init.body as ArrayBuffer).toString("utf8");
    expect(target).toBe("http://agentregistry:8080/v0/apply");
    expect(init.method).toBe("POST");
    expect(headers.get("authorization")).toBe("Bearer omtk_token");
    expect(headers.get("content-type")).toBe("application/yaml");
    expect(forwardedBody).toBe("kind: Skill\nmetadata:\n  name: demo\n");
  });
});
