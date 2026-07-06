import {
  claudeInstallSteps,
  claudeMcpAddCommand,
  installLocalCommand,
  mcpSseUrl,
  provisionPrompt,
} from "@/lib/mcp-install";

describe("mcp-install", () => {
  const base = "http://192.168.3.213:8765";
  const host = "${COMPUTERNAME:-${HOSTNAME:-$(hostname)}}";

  it("mcpSseUrl sem grupo não adiciona query string", () => {
    expect(mcpSseUrl(base, "openmemory", host)).toBe(
      `${base}/mcp/openmemory/sse/${host}`,
    );
  });

  it("mcpSseUrl com grupo anexa ?group= na instalação", () => {
    expect(mcpSseUrl(base, "claude", host, "Fiscal")).toBe(
      `${base}/mcp/claude/sse/${host}?group=Fiscal`,
    );
  });

  it("PowerShell usa ${env:COMPUTERNAME} antes de ?token=", () => {
    const psHost = "${env:COMPUTERNAME}";
    expect(mcpSseUrl(base, "cursor", psHost, "Fiscal", "omtk_abc")).toBe(
      `${base}/mcp/cursor/sse/\${env:COMPUTERNAME}?token=omtk_abc&group=Fiscal`,
    );
  });

  it("installLocalCommand inclui grupo na URL de instalação", () => {
    const cmd = installLocalCommand(base, "claude", host, "Fiscal");
    expect(cmd).toContain("?group=Fiscal");
    expect(cmd).toContain("--client claude");
  });

  it("claudeMcpAddCommand inclui ?group= no HTTP MCP", () => {
    expect(claudeMcpAddCommand(base, host, "Fiscal")).toContain("?group=Fiscal");
  });

  it("provisionPrompt inclui group na URL de provision", () => {
    const prompt = provisionPrompt(base, "claude", "Fiscal");
    expect(prompt).toContain("/provision?host=claude&group=Fiscal");
  });

  it("claudeInstallSteps propaga grupo nos 3 passos", () => {
    const steps = claudeInstallSteps(base, host, "Fiscal");
    expect(steps[0].command).toContain("?group=Fiscal");
    expect(steps[1].command).toContain("?group=Fiscal");
    expect(steps[2].command).toContain("&group=Fiscal");
  });
});
