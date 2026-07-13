"use client";

import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

export async function copyText(text: string): Promise<void> {
  if (navigator?.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

interface CommandBlockProps {
  label: string;
  command: string;
  copyKey: string;
  copiedKey: string | null;
  onCopied: (key: string) => void;
  variant?: "command" | "instruction";
}

export function CommandBlock({
  label,
  command,
  copyKey,
  copiedKey,
  onCopied,
  variant = "command",
}: CommandBlockProps) {
  const isInstruction = variant === "instruction";

  return (
    <div className="space-y-2">
      <p className="text-ui-label font-black uppercase tracking-widest text-slate-500">{label}</p>
      <div className="relative">
        {isInstruction ? (
          <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4 pr-14 text-ui-body-sm leading-relaxed text-slate-300">
            {command}
          </div>
        ) : (
          <pre className="custom-scroll overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 pr-14 font-mono text-ui-body-sm text-slate-300">
            <code className="whitespace-pre-wrap break-all">{command}</code>
          </pre>
        )}
        <button
          type="button"
          className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-lg border border-slate-700 bg-slate-800 text-slate-400 transition-colors hover:border-blue-500/40 hover:bg-slate-700 hover:text-blue-300"
          aria-label={`Copiar ${label}`}
          onClick={() => {
            copyText(command).then(() => onCopied(copyKey));
          }}
        >
          {copiedKey === copyKey ? (
            <Check className="h-4 w-4 text-emerald-400" />
          ) : (
            <Copy className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  );
}
