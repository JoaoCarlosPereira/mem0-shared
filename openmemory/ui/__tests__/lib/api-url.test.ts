import { fetchMcpBaseUrl, getMcpBaseUrl } from "@/lib/api-url";

describe("api-url", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
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
