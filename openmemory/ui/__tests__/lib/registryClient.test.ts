jest.mock("@/lib/api-client", () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

import { apiClient } from "@/lib/api-client";
import {
  buildPublishManifest,
  buildRegistryResourcePath,
  getRegistryResource,
  listRegistryResources,
  publishRegistryManifest,
  registryDependencySummary,
  registryResourceDescription,
  registryResourceSearchText,
  registrySourceSummary,
  validatePublishDraft,
  type RegistryResource,
} from "@/lib/registry-client";

const mockedApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe("registry-client", () => {
  beforeEach(() => {
    mockedApiClient.get.mockReset();
    mockedApiClient.post.mockReset();
  });

  it("monta URLs de list/detail com segmentos codificados", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: { items: [] },
    });

    await listRegistryResources("skills");

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      "/registry-api/v0/skills",
      expect.objectContaining({
        params: expect.objectContaining({
          namespace: "all",
          latestOnly: true,
          limit: 100,
        }),
      }),
    );
    expect(buildRegistryResourcePath("skills", "team/skill", "v1")).toBe(
      "/registry-api/v0/skills/team%2Fskill/v1",
    );
  });

  it("busca detalhe preservando namespace quando informado", async () => {
    mockedApiClient.get.mockResolvedValueOnce({
      data: {
        kind: "Skill",
        metadata: { namespace: "team", name: "skill", tag: "v1" },
        spec: {},
      },
    });

    const detail = await getRegistryResource("skills", "skill", "v1", "team");

    expect(mockedApiClient.get).toHaveBeenCalledWith(
      "/registry-api/v0/skills/skill/v1",
      { params: { namespace: "team" } },
    );
    expect(detail.registryKind).toBe("skills");
  });

  it("publica manifesto via /registry-api/v0/apply como YAML", async () => {
    mockedApiClient.post.mockResolvedValueOnce({
      data: { results: [{ kind: "Skill", name: "demo", status: "created" }] },
    });

    const response = await publishRegistryManifest("kind: Skill\n");

    expect(mockedApiClient.post).toHaveBeenCalledWith(
      "/registry-api/v0/apply",
      "kind: Skill\n",
      { headers: { "content-type": "application/yaml" } },
    );
    expect(response.results?.[0].status).toBe("created");
  });

  it("gera manifesto mínimo e valida campos obrigatórios", () => {
    expect(
      validatePublishDraft({
        kind: "skills",
        name: "",
        tag: "latest",
        title: "",
        description: "",
        sourceRepository: "",
        promptContent: "",
      }),
    ).toEqual([
      "Informe o nome do recurso.",
      "Informe um título curto.",
      "Informe a URL do repositório de origem.",
    ]);

    const manifest = buildPublishManifest({
      kind: "skills",
      name: "team/demo",
      tag: "v1",
      title: "Demo Skill",
      description: "Ajuda em tarefas repetitivas",
      sourceRepository: "https://github.com/acme/demo",
      promptContent: "",
    });

    expect(manifest).toContain("kind: Skill");
    expect(manifest).toContain('name: "team/demo"');
    expect(manifest).toContain('tag: "v1"');
    expect(manifest).toContain('url: "https://github.com/acme/demo"');
  });

  it("extrai texto de busca, origem e dependências úteis", () => {
    const resource: RegistryResource = {
      registryKind: "agents",
      kind: "Agent",
      metadata: {
        name: "agent",
        tag: "latest",
        labels: { team: "platform" },
      },
      spec: {
        title: "Agente Demo",
        description: "Executa fluxos internos",
        source: {
          repository: {
            url: "https://github.com/acme/agent",
            branch: "main",
          },
        },
        skills: [{ name: "skill-a", tag: "v1" }],
        mcpServers: [{ name: "mcp-a" }],
      },
    };

    expect(registryResourceDescription(resource)).toBe("Executa fluxos internos");
    expect(registryResourceSearchText(resource)).toContain("platform");
    expect(registrySourceSummary(resource)).toEqual([
      "Repositório: https://github.com/acme/agent (main)",
    ]);
    expect(registryDependencySummary(resource)).toEqual([
      "Skill: skill-a@v1",
      "MCP: mcp-a",
    ]);
  });
});
