import React from "react";
import { adrHeadingId } from "@/lib/markdownAdrLinks";

type MdComponents = {
  a?: (props: {
    href?: string;
    children?: React.ReactNode;
    [key: string]: unknown;
  }) => React.ReactNode;
  h2?: (props: { children?: React.ReactNode; [key: string]: unknown }) => React.ReactNode;
  h3?: (props: { children?: React.ReactNode; [key: string]: unknown }) => React.ReactNode;
  h4?: (props: { children?: React.ReactNode; [key: string]: unknown }) => React.ReactNode;
};

/**
 * Mock leve de react-markdown para Jest: interpreta headings/listas/negrito
 * o suficiente para asserts de UI sem carregar a árvore ESM.
 * Respeita `components` (a/h2/h3/h4) quando o MarkdownViewer os passa.
 */
export default function ReactMarkdown({
  children,
  components,
}: {
  children?: string;
  components?: MdComponents;
}) {
  const raw = String(children ?? "");
  const lines = raw.split("\n");
  const nodes: React.ReactNode[] = [];

  const renderInline = (text: string, keyBase: string): React.ReactNode[] => {
    const parts = text.split(/(\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*)/g);
    return parts.map((part, pi) => {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
      if (link) {
        const label = link[1];
        const href = link[2];
        if (components?.a) {
          return (
            <React.Fragment key={`${keyBase}-a-${pi}`}>
              {components.a({ href, children: label })}
            </React.Fragment>
          );
        }
        return (
          <a key={`${keyBase}-a-${pi}`} href={href}>
            {label}
          </a>
        );
      }
      const bold = /^\*\*(.+)\*\*$/.exec(part);
      if (bold) return <strong key={`${keyBase}-b-${pi}`}>{bold[1]}</strong>;
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length as 1 | 2 | 3 | 4 | 5 | 6;
      const title = heading[2];
      const headingProps = { children: title };
      if (level === 2 && components?.h2) {
        nodes.push(
          <React.Fragment key={i}>{components.h2(headingProps)}</React.Fragment>,
        );
      } else if (level === 3 && components?.h3) {
        nodes.push(
          <React.Fragment key={i}>{components.h3(headingProps)}</React.Fragment>,
        );
      } else if (level === 4 && components?.h4) {
        nodes.push(
          <React.Fragment key={i}>{components.h4(headingProps)}</React.Fragment>,
        );
      } else {
        const Tag = `h${level}` as keyof React.JSX.IntrinsicElements;
        const id = adrHeadingId(title);
        nodes.push(React.createElement(Tag, { key: i, id }, title));
      }
      continue;
    }
    if (/^\|/.test(line) && lines[i + 1] && /^\|\s*-+/.test(lines[i + 1])) {
      const headers = line
        .split("|")
        .map((c) => c.trim())
        .filter(Boolean);
      i += 1; // skip separator
      const rows: string[][] = [];
      while (i + 1 < lines.length && /^\|/.test(lines[i + 1])) {
        i += 1;
        rows.push(
          lines[i]
            .split("|")
            .map((c) => c.trim())
            .filter(Boolean),
        );
      }
      nodes.push(
        <table key={`t-${i}`}>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri}>
                {row.map((cell, ci) => (
                  <td key={ci}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>,
      );
      continue;
    }
    if (/^[-*]\s+/.test(line)) {
      const body = line.replace(/^[-*]\s+/, "");
      nodes.push(<li key={i}>{renderInline(body, `li-${i}`)}</li>);
      continue;
    }
    if (line.trim()) {
      nodes.push(<p key={i}>{renderInline(line, `p-${i}`)}</p>);
    }
  }

  return <>{nodes}</>;
}
