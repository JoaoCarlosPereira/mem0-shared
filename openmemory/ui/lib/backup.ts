// Helpers puros do fluxo de backup (task_08). Mantidos fora do componente para
// serem testáveis isoladamente (confirmação forte de restore, estado de RPO).

// Limite padrão de RPO (24h) — acima disso o último backup é considerado
// "desatualizado" na UI (alinhado ao PRD/TechSpec, alerta via UI + Prometheus).
export const DEFAULT_RPO_THRESHOLD_SECONDS = 24 * 3600;

/** Restore só é habilitado quando o texto de confirmação bate exatamente com o nome do backup. */
export function canRestore(confirmText: string, archiveName: string): boolean {
  return archiveName.length > 0 && confirmText.trim() === archiveName;
}

/** Último backup está desatualizado quando a idade (RPO) excede o limite. */
export function isStale(
  rpoAgeSeconds: number | null,
  threshold: number = DEFAULT_RPO_THRESHOLD_SECONDS,
): boolean {
  return rpoAgeSeconds !== null && rpoAgeSeconds > threshold;
}

/** Retenção válida: inteiro entre 1 e 50 (espelha BackupPolicySchema do backend). */
export function isValidRetention(n: number): boolean {
  return Number.isInteger(n) && n >= 1 && n <= 50;
}
