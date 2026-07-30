/**
 * Helpers for ADR links/anchors in shared Spec markdown.
 * Relative `adrs/adr-NNN.md` paths are legacy (local-only files) and must not
 * navigate to Next.js routes that 404 under `/docs/...`.
 */

const ADR_FILE_HREF =
  /^(?:\.\.\/)*(?:\.\/)?adrs\/(adr-\d{3})\.md(?:#.*)?$/i;
const ADR_HEADING =
  /^ADR-(\d{3})\b/i;

/** If href is a legacy local ADR path, return `#adr-NNN`; else null. */
export function adrHrefToAnchor(href: string | undefined | null): string | null {
  if (!href) return null;
  const trimmed = href.trim();
  const m = ADR_FILE_HREF.exec(trimmed);
  if (!m) return null;
  return `#${m[1].toLowerCase()}`;
}

/** Stable id for headings like `### ADR-007: Título` → `adr-007`. */
export function adrHeadingId(text: string): string | undefined {
  const plain = text.replace(/\s+/g, " ").trim();
  const m = ADR_HEADING.exec(plain);
  if (!m) return undefined;
  return `adr-${m[1]}`;
}
