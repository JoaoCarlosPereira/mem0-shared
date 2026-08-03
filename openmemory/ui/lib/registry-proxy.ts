const REGISTRY_CATALOG_RESOURCES = new Set([
  "agents",
  "mcpservers",
  "skills",
  "prompts",
  "plugins",
  "models",
]);

function normalizeSegments(pathSegments: string[]): string[] {
  return pathSegments.map((segment) => segment.trim()).filter(Boolean);
}

export function registryInternalBase(): string {
  return (
    process.env.AGENT_REGISTRY_INTERNAL_URL ||
    process.env.REGISTRY_INTERNAL_URL ||
    "http://agentregistry:8080"
  ).replace(/\/$/, "");
}

export function hasRegistryAuthorization(headers: Headers): boolean {
  const value = headers.get("authorization")?.trim();
  return !!value && /^Bearer\s+\S+\s*$/i.test(value);
}

export function isRegistryProxyPathAllowed(
  method: string,
  pathSegments: string[],
): boolean {
  const normalizedMethod = method.toUpperCase();
  const segments = normalizeSegments(pathSegments);

  if (normalizedMethod === "GET") {
    return (
      isNativeCatalogReadAllowed(segments) ||
      isMcpRegistryCompatReadAllowed(segments)
    );
  }

  if (normalizedMethod === "POST") {
    return segments.length === 2 && segments[0] === "v0" && segments[1] === "apply";
  }

  return false;
}

export function registryProxyTarget(
  baseUrl: string,
  pathSegments: string[],
  search: string,
): string {
  const suffix = normalizeSegments(pathSegments)
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  return `${baseUrl}${suffix ? `/${suffix}` : ""}${search}`;
}

function isNativeCatalogReadAllowed(pathSegments: string[]): boolean {
  if (pathSegments.length < 2 || pathSegments.length > 4) return false;
  if (pathSegments[0] !== "v0") return false;
  return REGISTRY_CATALOG_RESOURCES.has(pathSegments[1]);
}

function isMcpRegistryCompatReadAllowed(pathSegments: string[]): boolean {
  if (pathSegments[0] !== "v0.1" || pathSegments[1] !== "servers") {
    return false;
  }
  if (pathSegments.length === 2) return true;
  if (pathSegments.length === 4 && pathSegments[3] === "versions") return true;
  if (pathSegments.length === 5 && pathSegments[3] === "versions") return true;
  return false;
}
