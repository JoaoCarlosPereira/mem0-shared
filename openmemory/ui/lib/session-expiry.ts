/** Callback único para expirar sessão quando a API retorna 401. */
let onSessionExpired: (() => void) | null = null;
let expiryNotified = false;

export function registerSessionExpiryHandler(handler: () => void): () => void {
  onSessionExpired = handler;
  expiryNotified = false;
  return () => {
    if (onSessionExpired === handler) {
      onSessionExpired = null;
    }
  };
}

export function notifySessionExpired(): void {
  if (expiryNotified || !onSessionExpired) {
    return;
  }
  expiryNotified = true;
  onSessionExpired();
}

export function resetSessionExpiryGuard(): void {
  expiryNotified = false;
}
