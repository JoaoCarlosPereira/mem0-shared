/**
 * MCP install URLs/commands for agent machines (not the OpenMemory server).
 *
 * The last path segment is the client hostname (ADR-003 attribution). Commands
 * use shell env vars so each machine resolves its own name at install time.
 *
 * O parâmetro ``?group=`` na URL MCP vincula a equipe na **primeira conexão**
 * (instalação do plugin). Leituras e escritas posteriores usam o cadastro em
 * ``users.group_id`` — não é preciso enviar o grupo de novo.
 */

/** Bash / Git Bash / WSL / macOS — expands when pasted in the terminal. */
export const HOSTNAME_SHELL_BASH = "${COMPUTERNAME:-${HOSTNAME:-$(hostname)}}";

/** Windows PowerShell — expands when pasted in PowerShell. */
export const HOSTNAME_SHELL_PS = '$env:COMPUTERNAME';

export function mcpSsePath(client: string, hostnameExpr: string): string {
  return `/mcp/${client}/sse/${hostnameExpr}`;
}

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

export function mcpHttpUrl(
  baseUrl: string,
  client: string,
  hostnameExpr: string,
  group?: string,
): string {
  return `${baseUrl.replace(/\/$/, "")}/mcp/${client}/http/${hostnameExpr}${groupQuery(group)}`;
}

/** Claude Code CLI — registra o servidor MCP HTTP no escopo do usuário. */
export function claudeMcpAddCommand(
  baseUrl: string,
  hostnameExpr: string,
  group?: string,
): string {
  const url = mcpHttpUrl(baseUrl, "claude-code", hostnameExpr, group);
  return `claude mcp add --transport http mem0 "${url}" --scope user`;
}

/** Prompt para o agente executar a receita de provisionamento via curl. */
export function provisionPrompt(baseUrl: string, host = "claude", group?: string): string {
  const base = baseUrl.replace(/\/$/, "");
  const trimmed = (group ?? "").trim();
  const groupParam = trimmed ? `&group=${encodeURIComponent(trimmed)}` : "";
  return (
    `Leia ${base}/provision?host=${host}${groupParam} via curl e execute a receita retornada: ` +
    "escreva o bloco MCP no arquivo indicado (substituindo {hostname} pelo hostname desta máquina), " +
    'defina as variáveis de ambiente do campo "env", apresente ao usuário as 3 opções de modo de memória ' +
    "(transforme em hook global) e grave a escolha. Confirme cada ação mutante com o usuário antes de executar."
  );
}

export type ClaudeInstallStep = {
  step: number;
  title: string;
  command: string;
};

/** Passos ordenados da instalação Claude (npx → mcp add → provisionamento). */
export function claudeInstallSteps(
  baseUrl: string,
  hostnameExpr: string,
  group?: string,
): ClaudeInstallStep[] {
  return [
    {
      step: 1,
      title: "Instalar plugin e hooks",
      command: installLocalCommand(baseUrl, "claude", hostnameExpr, group),
    },
    {
      step: 2,
      title: "Registrar servidor MCP HTTP",
      command: claudeMcpAddCommand(baseUrl, hostnameExpr, group),
    },
    {
      step: 3,
      title: "Provisionamento via agente",
      command: provisionPrompt(baseUrl, "claude", group),
    },
  ];
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
] as const;
