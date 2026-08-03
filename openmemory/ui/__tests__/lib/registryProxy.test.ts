import {
  hasRegistryAuthorization,
  isRegistryProxyPathAllowed,
  registryProxyTarget,
} from "@/lib/registry-proxy";

describe("registry proxy allowlist", () => {
  it("permite leituras de catálogo nativo", () => {
    expect(isRegistryProxyPathAllowed("GET", ["v0", "skills"])).toBe(true);
    expect(isRegistryProxyPathAllowed("GET", ["v0", "mcpservers", "sysmo"])).toBe(
      true,
    );
    expect(
      isRegistryProxyPathAllowed("GET", ["v0", "agents", "team/agent", "latest"]),
    ).toBe(true);
    expect(
      isRegistryProxyPathAllowed("GET", ["v0", "prompts", "assist", "tags"]),
    ).toBe(true);
  });

  it("permite leitura compatível do MCP Registry v0.1", () => {
    expect(isRegistryProxyPathAllowed("GET", ["v0.1", "servers"])).toBe(true);
    expect(
      isRegistryProxyPathAllowed("GET", [
        "v0.1",
        "servers",
        "team/server",
        "versions",
      ]),
    ).toBe(true);
    expect(
      isRegistryProxyPathAllowed("GET", [
        "v0.1",
        "servers",
        "team/server",
        "versions",
        "latest",
      ]),
    ).toBe(true);
  });

  it("permite somente POST /v0/apply para publicação", () => {
    expect(isRegistryProxyPathAllowed("POST", ["v0", "apply"])).toBe(true);
    expect(isRegistryProxyPathAllowed("POST", ["v0", "skills"])).toBe(false);
    expect(isRegistryProxyPathAllowed("DELETE", ["v0", "apply"])).toBe(false);
  });

  it("nega endpoints fora do catálogo seguro", () => {
    expect(isRegistryProxyPathAllowed("GET", ["v0", "deployments"])).toBe(false);
    expect(isRegistryProxyPathAllowed("GET", ["v0", "runtimes"])).toBe(false);
    expect(isRegistryProxyPathAllowed("PUT", ["v0", "skills", "x"])).toBe(false);
    expect(isRegistryProxyPathAllowed("PATCH", ["v0", "skills", "x"])).toBe(false);
    expect(isRegistryProxyPathAllowed("DELETE", ["v0", "skills", "x"])).toBe(false);
  });
});

describe("registry proxy auth and target helpers", () => {
  it("aceita apenas Authorization Bearer preenchido", () => {
    expect(
      hasRegistryAuthorization(new Headers({ authorization: "Bearer jwt" })),
    ).toBe(true);
    expect(
      hasRegistryAuthorization(new Headers({ authorization: "Bearer local" })),
    ).toBe(true);
    expect(
      hasRegistryAuthorization(new Headers({ authorization: "Bearer omtk_abc" })),
    ).toBe(true);
    expect(hasRegistryAuthorization(new Headers())).toBe(false);
    expect(hasRegistryAuthorization(new Headers({ authorization: "Basic x" }))).toBe(
      false,
    );
    expect(hasRegistryAuthorization(new Headers({ authorization: "Bearer   " }))).toBe(
      false,
    );
  });

  it("monta URL upstream preservando segmentos com barra codificada", () => {
    expect(
      registryProxyTarget(
        "http://agentregistry:8080",
        ["v0", "skills", "team/skill", "latest"],
        "?namespace=all",
      ),
    ).toBe("http://agentregistry:8080/v0/skills/team%2Fskill/latest?namespace=all");
  });
});
