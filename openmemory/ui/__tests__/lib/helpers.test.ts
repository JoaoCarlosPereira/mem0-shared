import { formatDate, toDate } from "@/lib/helpers";

describe("formatDate", () => {
  it("formata timestamps em milissegundos (Date.getTime)", () => {
    const ms = new Date("2026-06-20T10:00:00Z").getTime();
    const result = formatDate(ms);
    expect(result).not.toBe("Agora");
    expect(result).toMatch(/jun|2026|dia|hora|minuto/i);
  });

  it("formata timestamps em segundos Unix", () => {
    const seconds = Math.floor(new Date("2026-06-20T10:00:00Z").getTime() / 1000);
    const result = formatDate(seconds);
    expect(result).not.toBe("Agora");
    expect(result).toMatch(/jun|2026|dia|hora|minuto/i);
  });

  it("formata strings ISO", () => {
    const result = formatDate("2026-06-20T10:00:00+00:00");
    expect(result).not.toBe("Agora");
  });

  it("toDate interpreta ms e segundos corretamente", () => {
    const iso = "2026-06-21T06:35:17.834714+00:00";
    const ms = new Date(iso).getTime();
    const seconds = Math.floor(ms / 1000);
    expect(toDate(ms)?.toISOString()).toBe(new Date(iso).toISOString());
    expect(toDate(seconds)?.toISOString()).toBe(new Date(iso).toISOString());
  });
});
