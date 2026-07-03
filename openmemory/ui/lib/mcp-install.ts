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

/**
 * Query string das URLs MCP. O ``?token=`` (credencial do usuário — feature
 * auth Google, ADR-003) vem primeiro; ``?group=`` mantém o vínculo de equipe
 * na primeira conexão. Ambos opcionais — sem eles a URL é o fluxo legado.
 */
function mcpQuery(group?: string, token?: string): string {
  const parts: string[] = [];
  const tok = (token ?? "").trim();
  if (tok) parts.push(`token=${encodeURIComponent(tok)}`);
  const trimmed = (group ?? "").trim();
  if (trimmed) parts.push(`group=${encodeURIComponent(trimmed)}`);
  return parts.length ? `?${parts.join("&")}` : "";
}

export function mcpSseUrl(
  baseUrl: string,
  client: string,
  hostnameExpr: string,
  group?: string,
  token?: string,
): string {
  return `${baseUrl.replace(/\/$/, "")}${mcpSsePath(client, hostnameExpr)}${mcpQuery(group, token)}`;
}

export function installLocalCommand(
  baseUrl: string,
  client: string,
  hostnameExpr: string,
  group?: string,
  token?: string,
): string {
  const url = mcpSseUrl(baseUrl, client, hostnameExpr, group, token);
  return `npx @openmemory/install local "${url}" --client ${client}`;
}

export function mcpHttpUrl(
  baseUrl: string,
  client: string,
  hostnameExpr: string,
  group?: string,
  token?: string,
): string {
  return `${baseUrl.replace(/\/$/, "")}/mcp/${client}/http/${hostnameExpr}${mcpQuery(group, token)}`;
}

/** Claude Code CLI — registra o servidor MCP HTTP no escopo do usuário. */
export function claudeMcpAddCommand(
  baseUrl: string,
  hostnameExpr: string,
  group?: string,
  token?: string,
): string {
  const url = mcpHttpUrl(baseUrl, "claude-code", hostnameExpr, group, token);
  return `claude mcp add --transport http mem0 "${url}" --scope user`;
}

/** Prompt para o agente executar a receita de provisionamento via curl. */
export function provisionPrompt(
  baseUrl: string,
  host = "claude",
  group?: string,
  token?: string,
): string {
  const base = baseUrl.replace(/\/$/, "");
  const trimmed = (group ?? "").trim();
  const groupParam = trimmed ? `&group=${encodeURIComponent(trimmed)}` : "";
  const tok = (token ?? "").trim();
  const tokenParam = tok ? `&token=${encodeURIComponent(tok)}` : "";
  return (
    `Leia ${base}/provision?host=${host}${groupParam}${tokenParam} via curl e execute a receita retornada: ` +
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
  token?: string,
): ClaudeInstallStep[] {
  return [
    {
      step: 1,
      title: "Instalar plugin e hooks",
      command: installLocalCommand(baseUrl, "claude", hostnameExpr, group, token),
    },
    {
      step: 2,
      title: "Registrar servidor MCP HTTP",
      command: claudeMcpAddCommand(baseUrl, hostnameExpr, group, token),
    },
    {
      step: 3,
      title: "Provisionamento via agente",
      command: provisionPrompt(baseUrl, "claude", group, token),
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
