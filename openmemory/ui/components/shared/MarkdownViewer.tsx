"use client";

import React, { useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";
import { adrHeadingId, adrHrefToAnchor } from "@/lib/markdownAdrLinks";

interface MarkdownViewerProps {
  content: string;
  className?: string;
  emptyLabel?: string;
  /** When set, clicks on `adrs/adr-NNN.md` open the shared ADRs document (not a local file). */
  onAdrLink?: (adrSlug: string) => void;
}

function childrenToPlainText(children: React.ReactNode): string {
  return React.Children.toArray(children)
    .map((child) => {
      if (typeof child === "string" || typeof child === "number") {
        return String(child);
      }
      if (React.isValidElement<{ children?: React.ReactNode }>(child)) {
        return childrenToPlainText(child.props.children);
      }
      return "";
    })
    .join("");
}

function buildMarkdownComponents(onAdrLink?: (adrSlug: string) => void): Components {
  return {
    a({ href, children, ...rest }) {
      const anchor = adrHrefToAnchor(href);
      if (anchor) {
        const adrSlug = anchor.slice(1);
        return (
          <a
            {...rest}
            href={anchor}
            title={
              onAdrLink
                ? "Abrir ADR no documento shared (adrs)"
                : "ADR neste documento (âncora local)"
            }
            onClick={(e) => {
              e.preventDefault();
              if (onAdrLink) {
                onAdrLink(adrSlug);
                return;
              }
              const el =
                typeof document !== "undefined"
                  ? document.getElementById(adrSlug)
                  : null;
              if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
              }
            }}
          >
            {children}
          </a>
        );
      }
      return (
        <a href={href} {...rest}>
          {children}
        </a>
      );
    },
    h2({ children, ...rest }) {
      const id = adrHeadingId(childrenToPlainText(children));
      return (
        <h2 {...rest} id={id}>
          {children}
        </h2>
      );
    },
    h3({ children, ...rest }) {
      const id = adrHeadingId(childrenToPlainText(children));
      return (
        <h3 {...rest} id={id}>
          {children}
        </h3>
      );
    },
    h4({ children, ...rest }) {
      const id = adrHeadingId(childrenToPlainText(children));
      return (
        <h4 {...rest} id={id}>
          {children}
        </h4>
      );
    },
  };
}

/**
 * Visualizador de Markdown (GFM) para specs/PRD/tasks — tema escuro do admin.
 * Links `adrs/adr-NNN.md` viram âncoras `#adr-NNN`; com `onAdrLink`, abrem o documento shared `adrs`.
 */
export function MarkdownViewer({
  content,
  className,
  emptyLabel = "(sem conteúdo)",
  onAdrLink,
}: MarkdownViewerProps) {
  const text = content?.trim() ? content : emptyLabel;
  const components = useMemo(
    () => buildMarkdownComponents(onAdrLink),
    [onAdrLink],
  );

  return (
    <div
      data-testid="markdown-viewer"
      className={cn(
        "markdown-viewer rounded-md border border-zinc-800 bg-zinc-900/60 p-4 text-sm leading-relaxed text-zinc-200",
        "[&_:first-child]:mt-0 [&_:last-child]:mb-0",
        "[&_h1]:mb-3 [&_h1]:mt-6 [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:text-zinc-50",
        "[&_h2]:mb-2 [&_h2]:mt-5 [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-zinc-50",
        "[&_h3]:mb-2 [&_h3]:mt-4 [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:text-zinc-100",
        "[&_h4]:mb-1.5 [&_h4]:mt-3 [&_h4]:text-base [&_h4]:font-semibold [&_h4]:text-zinc-100",
        "[&_p]:my-2 [&_p]:text-zinc-300",
        "[&_a]:text-blue-400 [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:text-blue-300",
        "[&_strong]:font-semibold [&_strong]:text-zinc-100",
        "[&_em]:italic",
        "[&_ul]:my-2 [&_ul]:list-disc [&_ul]:space-y-1 [&_ul]:pl-5",
        "[&_ol]:my-2 [&_ol]:list-decimal [&_ol]:space-y-1 [&_ol]:pl-5",
        "[&_li]:text-zinc-300",
        "[&_blockquote]:my-3 [&_blockquote]:border-l-2 [&_blockquote]:border-zinc-600 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-zinc-400",
        "[&_hr]:my-4 [&_hr]:border-zinc-700",
        "[&_code]:rounded [&_code]:bg-zinc-800 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_code]:text-amber-200",
        "[&_pre]:my-3 [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:border [&_pre]:border-zinc-700 [&_pre]:bg-zinc-950 [&_pre]:p-3",
        "[&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-zinc-200",
        "[&_table]:my-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-left [&_table]:text-xs",
        "[&_th]:border [&_th]:border-zinc-700 [&_th]:bg-zinc-800 [&_th]:px-2 [&_th]:py-1.5 [&_th]:font-semibold [&_th]:text-zinc-100",
        "[&_td]:border [&_td]:border-zinc-700 [&_td]:px-2 [&_td]:py-1.5 [&_td]:text-zinc-300",
        "[&_img]:my-3 [&_img]:max-w-full [&_img]:rounded-md",
        className,
      )}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

export default MarkdownViewer;
