import { canRestore, isStale, isValidRetention } from "@/lib/backup";

describe("canRestore", () => {
  it("habilita quando o texto bate exatamente com o nome do backup", () => {
    expect(canRestore("20260618-030000.zip", "20260618-030000.zip")).toBe(true);
  });
  it("desabilita quando o texto não bate", () => {
    expect(canRestore("errado", "20260618-030000.zip")).toBe(false);
  });
  it("desabilita quando não há backup selecionado", () => {
    expect(canRestore("", "")).toBe(false);
  });
  it("ignora espaços nas pontas da confirmação", () => {
    expect(canRestore("  20260618-030000.zip  ", "20260618-030000.zip")).toBe(true);
  });
});

describe("isStale", () => {
  it("considera desatualizado acima do limite de 24h", () => {
    expect(isStale(25 * 3600)).toBe(true);
  });
  it("não considera desatualizado dentro do limite", () => {
    expect(isStale(3600)).toBe(false);
  });
  it("null (sem backup) não é tratado como desatualizado pelo helper", () => {
    expect(isStale(null)).toBe(false);
  });
});

describe("isValidRetention", () => {
  it.each([1, 5, 50])("aceita %i", (n) => expect(isValidRetention(n)).toBe(true));
  it.each([0, 51, -1, 2.5])("rejeita %p", (n) => expect(isValidRetention(n)).toBe(false));
});
