import { plankaInternalBase, rewritePlankaRedirectLocation } from "@/lib/planka-proxy";

describe("planka proxy helpers", () => {
  it("resolve a base interna a partir de PLANKA_INTERNAL_URL", () => {
    const prev = process.env.PLANKA_INTERNAL_URL;
    process.env.PLANKA_INTERNAL_URL = "http://planka:1337/";
    expect(plankaInternalBase()).toBe("http://planka:1337");
    process.env.PLANKA_INTERNAL_URL = prev;
  });

  it("cai para PLANKA_BASE_URL quando PLANKA_INTERNAL_URL está ausente", () => {
    const prevInternal = process.env.PLANKA_INTERNAL_URL;
    const prevBase = process.env.PLANKA_BASE_URL;
    delete process.env.PLANKA_INTERNAL_URL;
    process.env.PLANKA_BASE_URL = "http://planka-legacy:1337";
    expect(plankaInternalBase()).toBe("http://planka-legacy:1337");
    process.env.PLANKA_INTERNAL_URL = prevInternal;
    process.env.PLANKA_BASE_URL = prevBase;
  });

  it("usa o default de rede Docker quando nenhuma env está definida", () => {
    const prevInternal = process.env.PLANKA_INTERNAL_URL;
    const prevBase = process.env.PLANKA_BASE_URL;
    delete process.env.PLANKA_INTERNAL_URL;
    delete process.env.PLANKA_BASE_URL;
    expect(plankaInternalBase()).toBe("http://planka:1337");
    process.env.PLANKA_INTERNAL_URL = prevInternal;
    process.env.PLANKA_BASE_URL = prevBase;
  });

  it("reescreve Location Docker-interno para same-origin /planka", () => {
    expect(
      rewritePlankaRedirectLocation(
        "http://planka:1337/boards/1",
        "http://planka:1337",
      ),
    ).toBe("/planka/boards/1");
  });

  it("reescreve Location absoluto com mesmo host mas base sem porta", () => {
    expect(
      rewritePlankaRedirectLocation(
        "http://planka:1337/api/projects?x=1",
        "http://planka:1337",
      ),
    ).toBe("/planka/api/projects?x=1");
  });

  it("prefixa Location relativo que ainda não começa com /planka", () => {
    expect(
      rewritePlankaRedirectLocation("/boards/1", "http://planka:1337"),
    ).toBe("/planka/boards/1");
  });

  it("não duplica o prefixo se o Location relativo já é /planka/...", () => {
    expect(
      rewritePlankaRedirectLocation("/planka/boards/1", "http://planka:1337"),
    ).toBe("/planka/boards/1");
  });

  it("repassa Location vazio ou de outro host sem alterar", () => {
    expect(rewritePlankaRedirectLocation("", "http://planka:1337")).toBe("");
    expect(
      rewritePlankaRedirectLocation(
        "https://outro-host.example/x",
        "http://planka:1337",
      ),
    ).toBe("https://outro-host.example/x");
  });
});
