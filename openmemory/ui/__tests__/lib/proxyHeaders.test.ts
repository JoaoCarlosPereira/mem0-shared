/**
 * Sanitização de headers do /api-proxy: remove hop-by-hop e content-length
 * antes de repassar ao upstream (fix do 500 atrás de nginx/Traefik).
 */
import {
  HOP_BY_HOP_HEADERS,
  rewriteUpstreamRedirectLocation,
  sanitizeUpstreamHeaders,
} from "@/lib/proxy-headers";

describe("sanitizeUpstreamHeaders", () => {
  it("remove todos os headers hop-by-hop e content-length", () => {
    const input = new Headers({
      host: "memorias.sysmo.com.br",
      connection: "upgrade",
      "keep-alive": "timeout=5",
      "transfer-encoding": "chunked",
      upgrade: "websocket",
      "content-length": "0",
      "proxy-connection": "keep-alive",
      te: "trailers",
    });
    const out = sanitizeUpstreamHeaders(input);
    for (const name of HOP_BY_HOP_HEADERS) {
      expect(out.has(name)).toBe(false);
    }
  });

  it("preserva headers de aplicação (Authorization, x-client-name, cookie)", () => {
    const input = new Headers({
      authorization: "Bearer jwt-abc",
      "x-client-name": "openmemory-ui",
      cookie: "session=1",
      connection: "keep-alive",
    });
    const out = sanitizeUpstreamHeaders(input);
    expect(out.get("authorization")).toBe("Bearer jwt-abc");
    expect(out.get("x-client-name")).toBe("openmemory-ui");
    expect(out.get("cookie")).toBe("session=1");
    expect(out.has("connection")).toBe(false);
  });

  it("não muta o objeto de entrada", () => {
    const input = new Headers({ connection: "close", authorization: "Bearer x" });
    sanitizeUpstreamHeaders(input);
    expect(input.get("connection")).toBe("close");
  });
});

describe("rewriteUpstreamRedirectLocation", () => {
  const internal = "http://openmemory-mcp:8765";

  it("reescreve Location absoluta da API interna para /api-proxy", () => {
    expect(
      rewriteUpstreamRedirectLocation(
        "http://openmemory-mcp:8765/api/v1/apps/?page=1",
        internal,
      ),
    ).toBe("/api-proxy/api/v1/apps/?page=1");
  });

  it("reescreve path relativo do upstream", () => {
    expect(rewriteUpstreamRedirectLocation("/api/v1/apps/", internal)).toBe(
      "/api-proxy/api/v1/apps/",
    );
  });

  it("mantém Location externa inalterada", () => {
    const external = "https://accounts.google.com/o/oauth2/v2/auth";
    expect(rewriteUpstreamRedirectLocation(external, internal)).toBe(external);
  });
});
