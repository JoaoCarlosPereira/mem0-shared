import axios from "axios";

import { apiClient } from "@/lib/api-client";

export const REGISTRY_RESOURCE_KINDS = [
  "skills",
  "mcpservers",
  "prompts",
  "agents",
  "plugins",
] as const;

export type RegistryResourceKind = (typeof REGISTRY_RESOURCE_KINDS)[number];

export const REGISTRY_KIND_LABELS: Record<RegistryResourceKind, string> = {
  skills: "Skills",
  mcpservers: "MCP servers",
  prompts: "Prompts",
  agents: "Agents",
  plugins: "Plugins",
};

export const REGISTRY_KIND_API_KIND: Record<RegistryResourceKind, string> = {
  skills: "Skill",
  mcpservers: "MCPServer",
  prompts: "Prompt",
  agents: "Agent",
  plugins: "Plugin",
};

export interface RegistryResource {
  apiVersion?: string;
  kind?: string;
  registryKind: RegistryResourceKind;
  metadata: {
    namespace?: string;
    name: string;
    tag?: string;
    labels?: Record<string, string>;
    annotations?: Record<string, string>;
    createdAt?: string;
    updatedAt?: string;
  };
  spec?: Record<string, unknown>;
  status?: unknown;
}

export interface RegistryListResponse {
  items?: RegistryResource[];
  nextCursor?: string;
}

export interface RegistryApplyResult {
  apiVersion?: string;
  kind?: string;
  namespace?: string;
  name: string;
  tag?: string;
  status: string;
  error?: string;
}

export interface RegistryApplyResponse {
  results?: RegistryApplyResult[];
}

export interface PublishDraft {
  kind: RegistryResourceKind;
  name: string;
  tag: string;
  title: string;
  description: string;
  sourceRepository: string;
  promptContent: string;
}

export function buildRegistryResourcePath(
  kind: RegistryResourceKind,
  name?: string,
  tag?: string,
): string {
  const segments = ["/registry-api/v0", kind];
  if (name) segments.push(encodeURIComponent(name));
  if (tag) segments.push(encodeURIComponent(tag));
  return segments.join("/");
}

export async function listRegistryResources(
  kind: RegistryResourceKind,
): Promise<RegistryResource[]> {
  const response = await apiClient.get<RegistryListResponse>(
    buildRegistryResourcePath(kind),
    {
      params: {
        namespace: "all",
        latestOnly: true,
        limit: 100,
      },
    },
  );
  return normalizeRegistryItems(kind, response.data?.items ?? []);
}

export async function listAllRegistryResources(): Promise<RegistryResource[]> {
  const grouped = await Promise.all(
    REGISTRY_RESOURCE_KINDS.map((kind) => listRegistryResources(kind)),
  );
  return grouped.flat();
}

export async function getRegistryResource(
  kind: RegistryResourceKind,
  name: string,
  tag?: string,
  namespace?: string,
): Promise<RegistryResource> {
  const response = await apiClient.get<RegistryResource>(
    buildRegistryResourcePath(kind, name, tag),
    namespace ? { params: { namespace } } : undefined,
  );
  return normalizeRegistryItem(kind, response.data);
}

export async function publishRegistryManifest(
  manifest: string,
): Promise<RegistryApplyResponse> {
  const response = await apiClient.post<RegistryApplyResponse>(
    "/registry-api/v0/apply",
    manifest,
    {
      headers: {
        "content-type": "application/yaml",
      },
    },
  );
  return response.data;
}

export const INSTALL_TARGETS = ["cursor", "claude", "codex"] as const;
export type InstallTarget = (typeof INSTALL_TARGETS)[number];

export const INSTALL_TARGET_LABELS: Record<InstallTarget, string> = {
  cursor: "Cursor",
  claude: "Claude Code",
  codex: "Codex",
};

export interface InstallRecipe {
  version: string;
  resource_kind: string;
  name: string;
  tag: string;
  target: InstallTarget | string;
  user_id?: string;
  steps?: Array<Record<string, unknown>>;
  rollback?: Array<Record<string, unknown>>;
  source?: Record<string, unknown>;
  resource?: RegistryResource;
}

const REGISTRY_KIND_TO_RECIPE_KIND: Record<RegistryResourceKind, string> = {
  skills: "skill",
  mcpservers: "mcpserver",
  prompts: "prompt",
  agents: "agent",
  plugins: "plugin",
};

export async function fetchInstallRecipe(input: {
  kind: RegistryResourceKind;
  name: string;
  tag: string;
  target: InstallTarget;
}): Promise<InstallRecipe> {
  const response = await apiClient.post<InstallRecipe>(
    "/api-proxy/api/v1/store/install-recipes",
    {
      kind: REGISTRY_KIND_TO_RECIPE_KIND[input.kind],
      name: input.name,
      tag: input.tag,
      target: input.target,
    },
  );
  return response.data;
}

export function normalizeRegistryItems(
  kind: RegistryResourceKind,
  items: RegistryResource[],
): RegistryResource[] {
  return items.map((item) => normalizeRegistryItem(kind, item));
}

export function normalizeRegistryItem(
  kind: RegistryResourceKind,
  item: RegistryResource,
): RegistryResource {
  return {
    ...item,
    registryKind: item.registryKind ?? kind,
    metadata: {
      ...item.metadata,
      name: item.metadata?.name ?? "",
    },
    spec: item.spec ?? {},
  };
}

export function registryResourceTitle(resource: RegistryResource): string {
  const specTitle = resource.spec?.title;
  return typeof specTitle === "string" && specTitle.trim()
    ? specTitle
    : resource.metadata.name;
}

export function registryResourceDescription(resource: RegistryResource): string {
  const description = resource.spec?.description;
  return typeof description === "string" && description.trim()
    ? description
    : "Sem descrição publicada.";
}

export function registryResourceTag(resource: RegistryResource): string {
  return resource.metadata.tag || "latest";
}

export function registryResourceNamespace(resource: RegistryResource): string {
  return resource.metadata.namespace || "default";
}

export function registryResourceSearchText(resource: RegistryResource): string {
  const labels = resource.metadata.labels
    ? Object.entries(resource.metadata.labels)
        .map(([key, value]) => `${key}=${value}`)
        .join(" ")
    : "";
  return [
    REGISTRY_KIND_LABELS[resource.registryKind],
    resource.kind,
    resource.metadata.name,
    registryResourceTitle(resource),
    registryResourceDescription(resource),
    labels,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function registrySourceSummary(resource: RegistryResource): string[] {
  const spec = resource.spec ?? {};
  const source = asRecord(spec.source);
  const remote = asRecord(spec.remote);
  const summaries: string[] = [];

  const repository = asRecord(source?.repository);
  const pluginGitRepository = asRecord(asRecord(asRecord(source?.git)?.repository));
  const packageSource = asRecord(source?.package);
  const packageOrigin = asRecord(packageSource?.origin);
  const agentImage = spec.source ? asRecord(spec.source)?.image : undefined;
  const pluginOci = asRecord(source?.oci);

  appendRepositorySummary(summaries, repository);
  appendRepositorySummary(summaries, pluginGitRepository);

  if (typeof agentImage === "string" && agentImage.trim()) {
    summaries.push(`Imagem: ${agentImage}`);
  }
  if (typeof packageOrigin?.identifier === "string" && packageOrigin.identifier.trim()) {
    summaries.push(`Pacote ${packageOrigin.type ?? ""}: ${packageOrigin.identifier}`);
  }
  if (typeof remote?.url === "string" && remote.url.trim()) {
    summaries.push(`Remoto ${remote.type ?? ""}: ${remote.url}`);
  }
  if (typeof pluginOci?.reference === "string" && pluginOci.reference.trim()) {
    summaries.push(`OCI: ${pluginOci.reference}`);
  }

  return summaries;
}

export function registryDependencySummary(resource: RegistryResource): string[] {
  const spec = resource.spec ?? {};
  const summaries: string[] = [];

  appendRefs(summaries, "Skill", spec.skills);
  appendRefs(summaries, "MCP", spec.mcpServers);
  appendRefs(summaries, "Plugin", spec.plugins);

  const instructions = asRecord(spec.instructions);
  if (instructions?.name) {
    summaries.push(`Instruções: ${String(instructions.name)}`);
  }

  return summaries;
}

export function validatePublishDraft(draft: PublishDraft): string[] {
  const errors: string[] = [];
  if (!REGISTRY_RESOURCE_KINDS.includes(draft.kind)) {
    errors.push("Escolha um tipo de recurso válido.");
  }
  if (!draft.name.trim()) {
    errors.push("Informe o nome do recurso.");
  }
  if (!draft.title.trim()) {
    errors.push("Informe um título curto.");
  }
  if (draft.kind === "prompts") {
    if (!draft.promptContent.trim()) {
      errors.push("Informe o conteúdo do prompt.");
    }
  } else if (!draft.sourceRepository.trim()) {
    errors.push("Informe a URL do repositório de origem.");
  }
  return errors;
}

export function buildPublishManifest(draft: PublishDraft): string {
  const tag = draft.tag.trim() || "latest";
  const apiKind = REGISTRY_KIND_API_KIND[draft.kind];
  const title = yamlScalar(draft.title.trim());
  const description = yamlScalar(draft.description.trim());
  const name = yamlScalar(draft.name.trim());
  const tagValue = yamlScalar(tag);
  const repositoryUrl = yamlScalar(draft.sourceRepository.trim());
  const promptContent = yamlBlock(draft.promptContent.trim());

  const lines = [
    "apiVersion: ar.dev/v1alpha1",
    `kind: ${apiKind}`,
    "metadata:",
    `  name: ${name}`,
    `  tag: ${tagValue}`,
    "spec:",
    `  title: ${title}`,
  ];

  if (draft.description.trim()) {
    lines.push(`  description: ${description}`);
  }

  if (draft.kind === "prompts") {
    lines.push("  content: |", promptContent);
    return lines.join("\n") + "\n";
  }

  if (draft.kind === "plugins") {
    lines.push(
      "  source:",
      "    type: git",
      "    git:",
      "      repository:",
      `        url: ${repositoryUrl}`,
    );
    return lines.join("\n") + "\n";
  }

  lines.push("  source:", "    repository:", `      url: ${repositoryUrl}`);
  return lines.join("\n") + "\n";
}

export function registryErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (error.response?.status === 401) {
      return "Sessão inválida ou ausente para acessar a Store.";
    }
    if (error.response?.status === 403) {
      return "Seu usuário não tem permissão para esta ação da Store.";
    }
    if (error.message) return error.message;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function appendRepositorySummary(
  summaries: string[],
  repository: Record<string, unknown> | undefined,
) {
  if (!repository || typeof repository.url !== "string" || !repository.url.trim()) {
    return;
  }
  const suffix = [repository.branch, repository.commit, repository.subfolder]
    .filter((value): value is string => typeof value === "string" && !!value.trim())
    .join(" · ");
  summaries.push(`Repositório: ${repository.url}${suffix ? ` (${suffix})` : ""}`);
}

function appendRefs(summaries: string[], label: string, refs: unknown) {
  if (!Array.isArray(refs)) return;
  for (const ref of refs) {
    const record = asRecord(ref);
    const name = record?.name;
    if (typeof name === "string" && name.trim()) {
      const tag = typeof record?.tag === "string" && record.tag.trim() ? `@${record.tag}` : "";
      summaries.push(`${label}: ${name}${tag}`);
    }
  }
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return undefined;
}

function yamlScalar(value: string): string {
  return JSON.stringify(value);
}

function yamlBlock(value: string): string {
  const content = value || " ";
  return content
    .split("\n")
    .map((line) => `    ${line}`)
    .join("\n");
}
