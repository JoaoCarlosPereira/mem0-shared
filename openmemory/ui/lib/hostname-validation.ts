/** Padrão Sysmo: S + 4 dígitos (ex.: S0281). */
export const SYSMO_HOSTNAME_PATTERN = /^S\d{4}$/i;

export const SYSMO_HOSTNAME_HINT =
  "Use apenas o nome/código da máquina no formato S + 4 dígitos (ex.: S0281). Não informe nome de pessoa ou equipe.";

export const SYSMO_HOSTNAME_ERROR = `Hostname inválido. ${SYSMO_HOSTNAME_HINT}`;

export function normalizeSysmoHostname(raw: string): string | null {
  const trimmed = raw.trim();
  if (!SYSMO_HOSTNAME_PATTERN.test(trimmed)) {
    return null;
  }
  return trimmed.toUpperCase();
}

export function isValidSysmoHostname(raw: string): boolean {
  return normalizeSysmoHostname(raw) !== null;
}
