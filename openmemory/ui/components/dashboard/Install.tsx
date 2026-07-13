"use client";

import React, { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import Image from "next/image";
import { Plug, Check, Copy } from "lucide-react";
import { fetchMcpBaseUrl, getMcpBaseUrl } from "@/lib/api-url";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";
import {
  claudeInstallSteps,
  installLocalCommand,
  installShellVariants,
  mcpSseUrl,
} from "@/lib/mcp-install";
import { PageHeader } from "@/components/shared/PageHeader";
import { GlassPanel } from "@/components/shared/GlassPanel";
import { CommandBlock, copyText } from "@/components/shared/CommandBlock";
import { ShellTabBar } from "@/components/shared/ShellTabs";
import { useImmutableAgentToken } from "@/hooks/useImmutableAgentToken";
import type { RootState } from "@/store/store";
import { cn } from "@/lib/utils";

const TOKEN_PLACEHOLDER = "SEU_TOKEN";

const clientTabs = [
  { key: "claude", label: "Claude", icon: "/images/claude.webp" },
  { key: "cursor", label: "Cursor", icon: "/images/cursor.png" },
] as const;

const allTabs = [
  { key: "mcp", label: "Link MCP", icon: "🔗" },
  ...clientTabs.map(({ key, label, icon }) => ({ key, label, icon })),
];

export const Install = () => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("claude");
  const linkedGroup = useSelector(
    (state: RootState) => state.profile.person?.group ?? null,
  );
  const [group, setGroup] = useState("");
  const groupLocked = Boolean(linkedGroup);
  const effectiveGroup = groupLocked ? linkedGroup! : group;
  const [mcpBase, setMcpBase] = useState(() => getMcpBaseUrl());
  const defaultShell = installShellVariants[0];

  useEffect(() => {
    if (linkedGroup) {
      setGroup(linkedGroup);
    }
  }, [linkedGroup]);

  const { rawToken } = useImmutableAgentToken();

  useEffect(() => {
    let cancelled = false;
    fetchMcpBaseUrl()
      .then((base) => {
        if (!cancelled) setMcpBase(base);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const tokenForCommands = rawToken ?? TOKEN_PLACEHOLDER;

  const markCopied = (key: string) => {
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Plug}
        title={`Instalar ${APP_NAME}`}
        description={APP_TAGLINE}
      />

      <GlassPanel accent="blue">
        <p className="text-ui-body-sm leading-relaxed text-slate-400">
          Execute o comando na máquina onde o Claude ou o Cursor está instalado. O
          hostname é resolvido automaticamente (
          <code className="font-mono text-slate-300">%COMPUTERNAME%</code>,{" "}
          <code className="font-mono text-slate-300">$env:COMPUTERNAME</code>,{" "}
          <code className="font-mono text-slate-300">$(hostname)</code>).
          {groupLocked ? (
            <>
              {" "}
              Sua conta já está no grupo abaixo — os comandos incluem{" "}
              <code className="font-mono text-slate-300">?group=</code> para vincular
              novas máquinas na primeira conexão MCP.
            </>
          ) : (
            <>
              {" "}
              Informe o grupo (equipe) abaixo — vinculado na primeira conexão MCP via{" "}
              <code className="font-mono text-slate-300">?group=</code>.
            </>
          )}
        </p>

        <div className="mt-5 max-w-md space-y-2">
          <label
            htmlFor="install-group"
            className="text-ui-label font-black uppercase tracking-widest text-slate-500"
          >
            {groupLocked
              ? "Grupo (equipe) — vinculado à sua conta"
              : "Grupo (equipe) — vazio usa Default"}
          </label>
          <input
            id="install-group"
            type="text"
            value={effectiveGroup}
            onChange={(e) => setGroup(e.target.value)}
            readOnly={groupLocked}
            aria-readonly={groupLocked}
            placeholder="ex.: Fiscal"
            className={cn(
              "w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm font-medium text-slate-200 placeholder:text-slate-600 focus:border-blue-500/50 focus:outline-none focus:ring-1 focus:ring-blue-500/50",
              groupLocked && "cursor-default opacity-90",
            )}
          />
        </div>
      </GlassPanel>

      {rawToken ? (
        <div
          data-testid="token-banner"
          className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-5"
        >
          <p className="text-ui-body-sm font-black uppercase tracking-widest text-amber-500/90">
            Token de agente
          </p>
          <p className="mt-2 text-ui-body-sm leading-relaxed text-slate-300">
            Fixo da sua conta — já embutido nos comandos abaixo. Identifica você nas
            leituras e gravações; use o mesmo token em todas as máquinas.
          </p>
          <div className="relative mt-3">
            <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60 px-4 py-3 pr-14 font-mono text-ui-body-sm text-slate-300">
              <code data-testid="raw-token" className="break-all">
                {rawToken}
              </code>
            </pre>
            <button
              type="button"
              className="absolute right-2 top-2 flex h-9 w-9 items-center justify-center rounded-lg border border-slate-700 bg-slate-800 text-slate-400 transition-colors hover:border-blue-500/40 hover:bg-slate-700 hover:text-blue-300"
              aria-label="Copiar token"
              onClick={() => copyText(rawToken).then(() => markCopied("raw-token"))}
            >
              {copiedKey === "raw-token" ? (
                <Check className="h-4 w-4 text-emerald-400" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-2xl border border-slate-800 glass">
        <ShellTabBar
          value={activeTab}
          onValueChange={setActiveTab}
          items={allTabs.map(({ key, label, icon }) => ({
            value: key,
            label,
            icon:
              typeof icon === "string" && icon.startsWith("/") ? (
                <span className="flex h-6 w-6 items-center justify-center overflow-hidden rounded-full border border-slate-700 bg-slate-800">
                  <Image src={icon} alt="" width={20} height={20} />
                </span>
              ) : (
                <span aria-hidden>{icon}</span>
              ),
          }))}
        />

        <div className="p-5 md:p-6">
          {activeTab === "mcp" ? (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-bold text-white">Link MCP</h3>
                <p className="mt-1 text-ui-body-sm uppercase tracking-widest text-slate-500">
                  URLs SSE para conectar manualmente
                </p>
              </div>
              <CommandBlock
                label={defaultShell.label}
                command={mcpSseUrl(
                  mcpBase,
                  "openmemory",
                  defaultShell.hostnameExpr,
                  effectiveGroup,
                  tokenForCommands,
                )}
                copyKey="mcp-ps"
                copiedKey={copiedKey}
                onCopied={markCopied}
              />
              <CommandBlock
                label={installShellVariants[1].label}
                command={mcpSseUrl(
                  mcpBase,
                  "openmemory",
                  installShellVariants[1].hostnameExpr,
                  effectiveGroup,
                  tokenForCommands,
                )}
                copyKey="mcp-bash"
                copiedKey={copiedKey}
                onCopied={markCopied}
              />
            </div>
          ) : null}

          {clientTabs.map(({ key }) =>
            activeTab === key ? (
              <div key={key} className="space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-white">
                    {key === "claude"
                      ? "Instalação — Claude"
                      : `Instalação — ${key.charAt(0).toUpperCase() + key.slice(1)}`}
                  </h3>
                  {key === "claude" ? (
                    <p className="mt-1 text-ui-body-sm uppercase tracking-widest text-slate-500">
                      Execute os passos na ordem, na máquina do agente
                    </p>
                  ) : null}
                </div>

                {key === "claude"
                  ? installShellVariants.map((variant) => (
                      <div key={`${key}-${variant.id}`} className="space-y-5">
                        <h4 className="text-ui-label font-black uppercase tracking-widest text-blue-400">
                          {variant.label}
                        </h4>
                        {claudeInstallSteps(
                          mcpBase,
                          variant.hostnameExpr,
                          effectiveGroup,
                          tokenForCommands,
                        ).map(({ step, title, command }) => (
                          <CommandBlock
                            key={`${key}-${variant.id}-step-${step}`}
                            label={`Passo ${step}: ${title}`}
                            command={command}
                            copyKey={`${key}-${variant.id}-step-${step}`}
                            copiedKey={copiedKey}
                            onCopied={markCopied}
                            variant={step === 3 ? "instruction" : "command"}
                          />
                        ))}
                      </div>
                    ))
                  : installShellVariants.map((variant) => (
                      <CommandBlock
                        key={`${key}-${variant.id}`}
                        label={variant.label}
                        command={installLocalCommand(
                          mcpBase,
                          key,
                          variant.hostnameExpr,
                          effectiveGroup,
                          tokenForCommands,
                        )}
                        copyKey={`${key}-${variant.id}`}
                        copiedKey={copiedKey}
                        onCopied={markCopied}
                      />
                    ))}
              </div>
            ) : null,
          )}
        </div>
      </div>
    </div>
  );
};

export default Install;
