import {
  fetchMcpBaseUrl,
  getApiUrl,
  getMcpBaseUrl,
  isUnusableMcpAdvertiseUrl,
} from "@/lib/api-url";

describe("api-url", () => {
  const originalFetch = global.fetch;
  const originalEnv = process.env.NEXT_PUBLIC_API_URL;

  afterEach(() => {
    global.fetch = originalFetch;
    if (originalEnv === undefined) {
      delete process.env.NEXT_PUBLIC_API_URL;
    } else {
      process.env.NEXT_PUBLIC_API_URL = originalEnv;
    }
    // @ts-expect-error test cleanup
    delete global.window;
  });

  it("getApiUrl no navegador sempre usa /api-proxy", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://openmemory-mcp:8765";
    Object.defineProperty(global, "window", {
      value: { location: { origin: "https://memorias.sysmo.com.br" } },
      writable: true,
    });
    expect(getApiUrl()).toBe("/api-proxy");
  });

  it("getApiUrl ignora URL absoluta de outra origem no navegador", () => {
    process.env.NEXT_PUBLIC_API_URL = "http://192.168.3.213:8765";
    Object.defineProperty(global, "window", {
      value: { location: { origin: "https://memorias.sysmo.com.br" } },
      writable: true,
    });
    expect(getApiUrl()).toBe("/api-proxy");
  });

  it("isUnusableMcpAdvertiseUrl detecta IP de bridge Docker", () => {
    expect(isUnusableMcpAdvertiseUrl("http://172.18.0.6:8765")).toBe(true);
    expect(isUnusableMcpAdvertiseUrl("http://192.168.3.213:8765")).toBe(false);
  });

  it("fetchMcpBaseUrl ignora discovery com IP Docker e usa NEXT_PUBLIC_MCP_URL", async () => {
    process.env.NEXT_PUBLIC_MCP_URL = "http://192.168.3.213:8765";
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ base_url: "http://172.18.0.6:8765" }),
    }) as typeof fetch;
    await expect(fetchMcpBaseUrl()).resolves.toBe("http://192.168.3.213:8765");
  });

  it("fetchMcpBaseUrl usa base_url do /discovery", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ base_url: "http://192.168.3.213:8765" }),
    }) as typeof fetch;

    await expect(fetchMcpBaseUrl()).resolves.toBe("http://192.168.3.213:8765");
    expect(global.fetch).toHaveBeenCalledWith("/api-proxy/discovery");
  });

  it("fetchMcpBaseUrl faz fallback quando /discovery falha", async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error("offline"));

    await expect(fetchMcpBaseUrl()).resolves.toBe(getMcpBaseUrl());
  });
});
