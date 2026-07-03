/**
 * Sanitização de headers do /api-proxy: remove hop-by-hop e content-length
 * antes de repassar ao upstream (fix do 500 atrás de nginx/Traefik).
 */
import {
  HOP_BY_HOP_HEADERS,
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
