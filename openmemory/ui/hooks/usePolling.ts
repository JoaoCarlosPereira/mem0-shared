import { useEffect } from "react";

/**
 * Executa `callback` a cada `intervalMs` milissegundos, pausando automaticamente
 * quando a aba do navegador está em background (Page Visibility API) e retomando
 * quando ela volta ao foco. Dispara também uma vez imediatamente ao montar.
 *
 * O consumidor DEVE passar uma `callback` estável (via `useCallback`) — o efeito
 * é recriado sempre que `callback`, `intervalMs` ou `enabled` mudam.
 *
 * Seguro em SSR/jsdom: só toca `document` quando ele existe.
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  enabled: boolean = true,
): void {
  useEffect(() => {
    if (!enabled) return;
    if (typeof document === "undefined") return;

    let active = true;
    // Só dispara quando a aba está visível; ao voltar ao foco o evento
    // `visibilitychange` chama `tick` e a callback roda imediatamente.
    const tick = () => {
      if (active && !document.hidden) {
        void callback();
      }
    };

    const id = setInterval(tick, intervalMs);
    document.addEventListener("visibilitychange", tick);
    tick();

    return () => {
      active = false;
      clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [callback, intervalMs, enabled]);
}

export default usePolling;
