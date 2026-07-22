import React from "react";

/**
 * Mock leve de react-markdown para Jest: interpreta headings/listas/negrito
 * o suficiente para asserts de UI sem carregar a árvore ESM.
 */
export default function ReactMarkdown({ children }: { children?: string }) {
  const raw = String(children ?? "");
  const lines = raw.split("\n");
  const nodes: React.ReactNode[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length as 1 | 2 | 3 | 4 | 5 | 6;
      const Tag = `h${level}` as keyof React.JSX.IntrinsicElements;
      nodes.push(React.createElement(Tag, { key: i }, heading[2]));
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
      nodes.push(
        <li key={i}>{line.replace(/^[-*]\s+/, "").replace(/\*\*(.+?)\*\*/g, "$1")}</li>,
      );
      continue;
    }
    if (line.trim()) {
      const parts = line.split(/(\*\*[^*]+\*\*)/g).map((part, pi) => {
        const bold = /^\*\*(.+)\*\*$/.exec(part);
        if (bold) return <strong key={pi}>{bold[1]}</strong>;
        return part;
      });
      nodes.push(<p key={i}>{parts}</p>);
    }
  }

  return <>{nodes}</>;
}
