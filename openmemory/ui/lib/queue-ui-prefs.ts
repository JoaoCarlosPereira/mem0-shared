/** Preferências locais da UI de filas (localStorage — não alteram o backend). */

const STORAGE_KEY = "mem0-admin-queue-ui-prefs-v1";

export type QueueKind = "write" | "governance";

export type QueueUiPrefs = {
  /** IDs de jobs com falha já vistos na página Filas (`write:uuid` / `governance:uuid`). */
  acknowledgedFailedIds: string[];
  /** Ocultar jobs com status done na tabela (por tipo de fila). */
  hideCompleted: Record<QueueKind, boolean>;
};

const DEFAULT_PREFS: QueueUiPrefs = {
  acknowledgedFailedIds: [],
  hideCompleted: { write: false, governance: false },
};

function loadRaw(): QueueUiPrefs {
  if (typeof window === "undefined") return { ...DEFAULT_PREFS };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_PREFS };
    const parsed = JSON.parse(raw) as Partial<QueueUiPrefs>;
    return {
      acknowledgedFailedIds: Array.isArray(parsed.acknowledgedFailedIds)
        ? parsed.acknowledgedFailedIds
        : [],
      hideCompleted: {
        write: parsed.hideCompleted?.write ?? false,
        governance: parsed.hideCompleted?.governance ?? false,
      },
    };
  } catch {
    return { ...DEFAULT_PREFS };
  }
}

function saveRaw(prefs: QueueUiPrefs): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
}

export function queueJobKey(kind: QueueKind, id: string): string {
  return `${kind}:${id}`;
}

export function getQueueUiPrefs(): QueueUiPrefs {
  return loadRaw();
}

export function acknowledgeFailedJobs(
  writeIds: string[],
  governanceIds: string[],
): QueueUiPrefs {
  const prefs = loadRaw();
  const next = new Set(prefs.acknowledgedFailedIds);
  for (const id of writeIds) next.add(queueJobKey("write", id));
  for (const id of governanceIds) next.add(queueJobKey("governance", id));
  const updated: QueueUiPrefs = {
    ...prefs,
    acknowledgedFailedIds: [...next],
  };
  saveRaw(updated);
  return updated;
}

export function countUnacknowledgedForKind(
  ids: string[],
  kind: QueueKind,
): number {
  const ack = new Set(loadRaw().acknowledgedFailedIds);
  let count = 0;
  for (const id of ids) {
    if (!ack.has(queueJobKey(kind, id))) count += 1;
  }
  return count;
}

export function countUnacknowledgedFailed(
  writeIds: string[],
  governanceIds: string[],
): number {
  return (
    countUnacknowledgedForKind(writeIds, "write") +
    countUnacknowledgedForKind(governanceIds, "governance")
  );
}

export function setHideCompleted(kind: QueueKind, hidden: boolean): QueueUiPrefs {
  const prefs = loadRaw();
  const updated: QueueUiPrefs = {
    ...prefs,
    hideCompleted: { ...prefs.hideCompleted, [kind]: hidden },
  };
  saveRaw(updated);
  return updated;
}

export function isHideCompleted(kind: QueueKind): boolean {
  return loadRaw().hideCompleted[kind];
}

/** Remove IDs reconhecidos que não existem mais entre os falhos atuais (limpeza). */
export function pruneAcknowledgedFailed(
  writeIds: string[],
  governanceIds: string[],
): void {
  const active = new Set<string>();
  for (const id of writeIds) active.add(queueJobKey("write", id));
  for (const id of governanceIds) active.add(queueJobKey("governance", id));
  const prefs = loadRaw();
  const pruned = prefs.acknowledgedFailedIds.filter((k) => active.has(k));
  if (pruned.length !== prefs.acknowledgedFailedIds.length) {
    saveRaw({ ...prefs, acknowledgedFailedIds: pruned });
  }
}
