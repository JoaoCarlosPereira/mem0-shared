/**
 * Mem0 Shared — detect SpecWorkspace iframe embed (?embed=1).
 * After client-side navigation the query string is dropped, so we also
 * persist a sessionStorage flag set at bootstrap.
 */

const STORAGE_KEY = 'mem0_embed';

export function markMem0Embed() {
  try {
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(STORAGE_KEY, '1');
    }
  } catch (_err) {
    // private mode / blocked storage
  }
}

export default function isMem0Embed() {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    if (new URLSearchParams(window.location.search).get('embed') === '1') {
      markMem0Embed();
      return true;
    }
    return sessionStorage.getItem(STORAGE_KEY) === '1';
  } catch (_err) {
    return false;
  }
}
