import { act, renderHook } from "@testing-library/react";

jest.mock("@/lib/registry-client", () => ({
  getRegistryResource: jest.fn(),
  listAllRegistryResources: jest.fn(),
  publishRegistryManifest: jest.fn(),
  fetchInstallRecipe: jest.fn(),
  registryErrorMessage: (error: unknown, fallback: string) =>
    error instanceof Error ? error.message : fallback,
}));

import {
  fetchInstallRecipe,
  getRegistryResource,
  listAllRegistryResources,
  publishRegistryManifest,
  type RegistryResource,
} from "@/lib/registry-client";
import { useRegistryCatalog } from "@/hooks/useRegistryCatalog";

const mockedListAllRegistryResources = listAllRegistryResources as jest.MockedFunction<
  typeof listAllRegistryResources
>;
const mockedGetRegistryResource = getRegistryResource as jest.MockedFunction<
  typeof getRegistryResource
>;
const mockedPublishRegistryManifest = publishRegistryManifest as jest.MockedFunction<
  typeof publishRegistryManifest
>;
const mockedFetchInstallRecipe = fetchInstallRecipe as jest.MockedFunction<
  typeof fetchInstallRecipe
>;

const skill: RegistryResource = {
  registryKind: "skills",
  kind: "Skill",
  metadata: { name: "demo", tag: "latest" },
  spec: { title: "Demo" },
};

describe("useRegistryCatalog", () => {
  beforeEach(() => {
    mockedListAllRegistryResources.mockReset();
    mockedGetRegistryResource.mockReset();
    mockedPublishRegistryManifest.mockReset();
    mockedFetchInstallRecipe.mockReset();
  });

  it("carrega catálogo e detalhe do recurso selecionado", async () => {
    mockedListAllRegistryResources.mockResolvedValueOnce([skill]);
    mockedGetRegistryResource.mockResolvedValueOnce(skill);

    const { result } = renderHook(() => useRegistryCatalog());

    await act(async () => {
      await result.current.loadCatalog();
    });

    expect(result.current.resources).toEqual([skill]);
    expect(result.current.error).toBeNull();

    await act(async () => {
      await result.current.loadDetail("skills", "demo", "latest");
    });

    expect(mockedGetRegistryResource).toHaveBeenCalledWith(
      "skills",
      "demo",
      "latest",
      undefined,
    );
    expect(result.current.selectedResource).toEqual(skill);
  });

  it("publica manifesto e recarrega catálogo", async () => {
    mockedPublishRegistryManifest.mockResolvedValueOnce({
      results: [{ kind: "Skill", name: "demo", status: "created" }],
    });
    mockedListAllRegistryResources.mockResolvedValueOnce([skill]);

    const { result } = renderHook(() => useRegistryCatalog());

    await act(async () => {
      await result.current.publishManifest("kind: Skill\n");
    });

    expect(mockedPublishRegistryManifest).toHaveBeenCalledWith("kind: Skill\n");
    expect(mockedListAllRegistryResources).toHaveBeenCalledTimes(1);
    expect(result.current.applyResponse?.results?.[0]).toEqual(
      expect.objectContaining({ status: "created" }),
    );
    expect(result.current.resources).toEqual([skill]);
  });

  it("registra erro de publicação sem lançar", async () => {
    mockedPublishRegistryManifest.mockRejectedValueOnce(new Error("denied"));

    const { result } = renderHook(() => useRegistryCatalog());

    await act(async () => {
      const response = await result.current.publishManifest("kind: Skill\n");
      expect(response).toBeNull();
    });

    expect(result.current.publishError).toBe("denied");
  });

  it("gera receita de instalação para o alvo escolhido", async () => {
    mockedFetchInstallRecipe.mockResolvedValueOnce({
      version: "1",
      resource_kind: "skill",
      name: "demo",
      tag: "latest",
      target: "claude",
      steps: [{ id: "copy-resource", type: "copy", to: "~/.claude/skills/demo" }],
    });

    const { result } = renderHook(() => useRegistryCatalog());

    await act(async () => {
      await result.current.requestInstallRecipe("skills", "demo", "latest", "claude");
    });

    expect(mockedFetchInstallRecipe).toHaveBeenCalledWith({
      kind: "skills",
      name: "demo",
      tag: "latest",
      target: "claude",
    });
    expect(result.current.installRecipe?.target).toBe("claude");
    expect(result.current.installError).toBeNull();
  });
});
