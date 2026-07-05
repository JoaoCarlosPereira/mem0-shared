import { normalizeHostname, resolveAttribution } from "@/lib/attribution";

describe("normalizeHostname", () => {
  it("strips ui: prefix from UI reads", () => {
    expect(normalizeHostname("ui:openmemory")).toBe("openmemory");
  });

  it("returns undefined for unknown sentinel", () => {
    expect(normalizeHostname("unknown")).toBeUndefined();
  });
});

describe("resolveAttribution", () => {
  it("prefers linked user display name over hostname", () => {
    const result = resolveAttribution({
      clientName: "cursor",
      hostname: "S0293",
      displayName: "João Silva",
      avatarUrl: "https://example.com/avatar.png",
    });
    expect(result.label).toBe("João Silva");
    expect(result.avatarUrl).toBe("https://example.com/avatar.png");
    expect(result.clientKey).toBe("cursor");
  });

  it("prefers hostname over client branding", () => {
    const result = resolveAttribution({
      clientName: "cursor",
      hostname: "S0293",
    });
    expect(result.label).toBe("S0293");
    expect(result.clientKey).toBe("cursor");
  });

  it("reads attribution from Qdrant metadata", () => {
    const result = resolveAttribution({
      appName: "sysmovs",
      metadata: {
        hostname: "maqA",
        mcp_client: "claude",
      },
    });
    expect(result.label).toBe("maqA");
    expect(result.clientKey).toBe("claude");
  });

  it("falls back to user_id in metadata when hostname is absent", () => {
    const result = resolveAttribution({
      appName: "sysmovs",
      metadata: {
        user_id: "S0293",
        mcp_client: "cursor",
      },
    });
    expect(result.label).toBe("S0293");
  });

  it("falls back to client name when hostname is missing", () => {
    const result = resolveAttribution({
      clientName: "cursor",
    });
    expect(result.label).toBe("Cursor");
  });

  it("maps claude-code to Claude branding", () => {
    const result = resolveAttribution({
      clientName: "claude-code",
      hostname: "S0293",
    });
    expect(result.label).toBe("S0293");
    expect(result.clientKey).toBe("claude");
  });
});
