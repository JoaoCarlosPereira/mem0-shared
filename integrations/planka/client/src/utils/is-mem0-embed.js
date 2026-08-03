/*!
 * Mem0 Shared — detect SpecWorkspace iframe embed (?embed=1).
 */

export default function isMem0Embed() {
  if (typeof window === 'undefined') {
    return false;
  }

  try {
    return new URLSearchParams(window.location.search).get('embed') === '1';
  } catch (_err) {
    return false;
  }
}
