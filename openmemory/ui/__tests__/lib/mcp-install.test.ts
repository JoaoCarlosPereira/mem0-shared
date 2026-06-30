import {
  installLocalCommand,
  mcpSseUrl,
} from "@/lib/mcp-install";

describe("mcp-install com grupo (task_07 / ADR-004)", () => {
  const base = "http://192.168.3.213:8765";
  const host = "${COMPUTERNAME:-${HOSTNAME:-$(hostname)}}";

  it("mcpSseUrl sem grupo não adiciona query string", () => {
    expect(mcpSseUrl(base, "openmemory", host)).toBe(
      `${base}/mcp/openmemory/sse/${host}`,
    );
  });

  it("mcpSseUrl com grupo anexa ?group= URL-encoded", () => {
    expect(mcpSseUrl(base, "openmemory", host, "Equipe Backend")).toBe(
      `${base}/mcp/openmemory/sse/${host}?group=Equipe%20Backend`,
    );
  });

  it("grupo vazio ou só espaços não adiciona o parâmetro", () => {
    expect(mcpSseUrl(base, "openmemory", host, "")).toBe(
      `${base}/mcp/openmemory/sse/${host}`,
    );
    expect(mcpSseUrl(base, "openmemory", host, "   ")).toBe(
      `${base}/mcp/openmemory/sse/${host}`,
    );
  });

  it("installLocalCommand inclui o grupo na URL e mantém --client", () => {
    const cmd = installLocalCommand(base, "claude", host, "Time Dados");
    expect(cmd).toContain("?group=Time%20Dados");
    expect(cmd).toContain("--client claude");
    expect(cmd.startsWith("npx @openmemory/install local")).toBe(true);
  });

  it("installLocalCommand sem grupo equivale ao comportamento anterior", () => {
    expect(installLocalCommand(base, "cursor", host)).toBe(
      `npx @openmemory/install local "${base}/mcp/cursor/sse/${host}" --client cursor`,
    );
  });

  it("grupo com acentos é corretamente URL-encoded", () => {
    expect(mcpSseUrl(base, "openmemory", host, "Inovação")).toContain(
      "?group=Inova%C3%A7%C3%A3o",
    );
  });
});
