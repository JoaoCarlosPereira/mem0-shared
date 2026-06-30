/**
 * MCP install URLs/commands for agent machines (not the OpenMemory server).
 *
 * The last path segment is the client hostname (ADR-003 attribution). Commands
 * use shell env vars so each machine resolves its own name at install time.
 */

/** Bash / Git Bash / WSL / macOS — expands when pasted in the terminal. */
export const HOSTNAME_SHELL_BASH = "${COMPUTERNAME:-${HOSTNAME:-$(hostname)}}";

/** Windows CMD — expands when pasted in cmd.exe. */
export const HOSTNAME_SHELL_CMD = "%COMPUTERNAME%";

/** Windows PowerShell — expands when pasted in PowerShell. */
export const HOSTNAME_SHELL_PS = '$env:COMPUTERNAME';

export function mcpSsePath(client: string, hostnameExpr: string): string {
  return `/mcp/${client}/sse/${hostnameExpr}`;
}

/**
 * Sufixo de query com o grupo (equipe) informado na instalação (ADR-004).
 * Vazio quando nenhum grupo é informado — mantém a URL inalterada e o backend
 * recai no grupo Default.
 */
function groupQuery(group?: string): string {
  const trimmed = (group ?? "").trim();
  return trimmed ? `?group=${encodeURIComponent(trimmed)}` : "";
}

export function mcpSseUrl(
  baseUrl: string,
  client: string,
  hostnameExpr: string,
  group?: string,
): string {
  return `${baseUrl.replace(/\/$/, "")}${mcpSsePath(client, hostnameExpr)}${groupQuery(group)}`;
}

export function installLocalCommand(
  baseUrl: string,
  client: string,
  hostnameExpr: string,
  group?: string,
): string {
  const url = mcpSseUrl(baseUrl, client, hostnameExpr, group);
  return `npx @openmemory/install local "${url}" --client ${client}`;
}

export const installShellVariants = [
  {
    id: "powershell",
    label: "Windows (PowerShell)",
    hostnameExpr: HOSTNAME_SHELL_PS,
  },
  {
    id: "bash",
    label: "Linux / macOS / Git Bash",
    hostnameExpr: HOSTNAME_SHELL_BASH,
  },
  {
    id: "cmd",
    label: "Windows (CMD)",
    hostnameExpr: HOSTNAME_SHELL_CMD,
  },
] as const;
