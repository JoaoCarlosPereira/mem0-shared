import {
  isValidSysmoHostname,
  normalizeSysmoHostname,
} from "@/lib/hostname-validation";

describe("hostname-validation", () => {
  it("aceita S + 4 dígitos", () => {
    expect(isValidSysmoHostname("S0281")).toBe(true);
    expect(normalizeSysmoHostname("s0293")).toBe("S0293");
  });

  it("rejeita sufixo com nome", () => {
    expect(isValidSysmoHostname("S0281 - Ana Paula")).toBe(false);
  });
});
