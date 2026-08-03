/*!
 * Mem0 Shared — avisa o shell Next.js da rota atual no iframe embed.
 * Permite URL compartilhável /docs/boards/:id sem remount do iframe.
 */

import isMem0Embed from './is-mem0-embed';

/**
 * @param {{ boardId?: string|null, cardId?: string|null, pathname?: string|null }} payload
 */
export default function notifyMem0ParentPath(payload = {}) {
  if (!isMem0Embed()) {
    return;
  }
  if (typeof window === 'undefined' || !window.parent || window.parent === window) {
    return;
  }

  try {
    window.parent.postMessage(
      {
        source: 'mem0-kanban',
        type: 'path',
        boardId: payload.boardId ? String(payload.boardId) : null,
        cardId: payload.cardId ? String(payload.cardId) : null,
        pathname: payload.pathname ? String(payload.pathname) : null,
      },
      window.location.origin,
    );
  } catch (_err) {
    // cross-origin / sandboxed — ignore
  }
}
