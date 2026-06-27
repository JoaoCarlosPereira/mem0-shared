import { constants } from "@/components/shared/source-app";

const UNKNOWN_HOSTS = new Set(["unknown", "unknown-host"]);

/** MCP client slugs that differ from UI icon keys in ``source-app.tsx``. */
const CLIENT_ALIASES: Record<string, keyof typeof constants> = {
  "claude-code": "claude",
  "claude_code": "claude",
  codex: "default",
  openmemory: "openmemory",
};

export function normalizeHostname(
  hostname?: string | null,
): string | undefined {
  if (!hostname) {
    return undefined;
  }
  const trimmed = hostname.trim();
  if (!trimmed || UNKNOWN_HOSTS.has(trimmed)) {
    return undefined;
  }
  if (trimmed.startsWith("ui:")) {
    return trimmed.slice(3) || undefined;
  }
  return trimmed;
}

export interface AttributionDisplay {
  label: string;
  clientKey: keyof typeof constants;
  iconImage?: string;
}

export function resolveAttribution(opts: {
  appName?: string | null;
  clientName?: string | null;
  hostname?: string | null;
  metadata?: Record<string, unknown> | null;
}): AttributionDisplay {
  const meta = opts.metadata ?? {};
  const hostname =
    normalizeHostname(opts.hostname) ??
    normalizeHostname(
      typeof meta.hostname === "string" ? meta.hostname : undefined,
    ) ??
    normalizeHostname(
      typeof meta.user_id === "string" ? meta.user_id : undefined,
    );

  const rawClient =
    opts.clientName ||
    (typeof meta.mcp_client === "string" ? meta.mcp_client : undefined) ||
    opts.appName ||
    undefined;

  const normalizedClient = rawClient?.trim().toLowerCase();
  const clientKey = (
    normalizedClient && normalizedClient in constants
      ? normalizedClient
      : normalizedClient && CLIENT_ALIASES[normalizedClient]
        ? CLIENT_ALIASES[normalizedClient]
        : "default"
  ) as keyof typeof constants;
  const appConfig = constants[clientKey] ?? constants.default;

  const label =
    hostname || appConfig.name || rawClient || opts.appName || "Desconhecido";

  return {
    label,
    clientKey,
    iconImage: appConfig.iconImage,
  };
}
