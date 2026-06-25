import {
  BRASILIA_TIMEZONE,
  formatDateTime,
  formatDateTimeFull,
  formatDateTimeShort,
} from "@/lib/datetime";

describe("datetime (Brasília)", () => {
  it("formata ISO UTC em dd/MM/yyyy HH:mm:ss de Brasília", () => {
    expect(formatDateTimeFull("2026-01-02T08:30:00Z")).toBe(
      "02/01/2026 05:30:00",
    );
  });

  it("formata epoch em segundos em horário de Brasília", () => {
    const seconds = Math.floor(
      new Date("2026-01-01T10:00:00Z").getTime() / 1000,
    );
    expect(formatDateTimeFull(seconds)).toBe("01/01/2026 07:00:00");
  });

  it("formata data/hora curta em Brasília", () => {
    expect(formatDateTimeShort("2026-06-20T10:00:00Z")).toBe(
      "20/06/2026 07:00",
    );
  });

  it("usa America/Sao_Paulo como fuso padrão", () => {
    expect(BRASILIA_TIMEZONE).toBe("America/Sao_Paulo");
  });

  it("formatDateTime inclui hora em Brasília", () => {
    const text = formatDateTime("2026-06-20T12:00:00Z");
    expect(text).toMatch(/20.*jun.*2026/i);
    expect(text).toMatch(/09:00|9:00/);
  });
});
