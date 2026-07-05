"use client";

import React, { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Copy, Check, Plug } from "lucide-react";
import Image from "next/image";
import { fetchMcpBaseUrl, getMcpBaseUrl } from "@/lib/api-url";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";
import {
  claudeInstallSteps,
  installLocalCommand,
  installShellVariants,
  mcpSseUrl,
} from "@/lib/mcp-install";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAgentTokenApi } from "@/hooks/useAgentTokenApi";
import type { RootState } from "@/store/store";

// Placeholder (fallback raro: sessão indisponível). Sem <> para sobreviver
// intacto ao encodeURIComponent das URLs.
const TOKEN_PLACEHOLDER = "SEU_TOKEN";

const clientTabs = [
  { key: "claude", label: "Claude", icon: "/images/claude.webp" },
  { key: "cursor", label: "Cursor", icon: "/images/cursor.png" },
];

const colorGradientMap: { [key: string]: string } = {
  claude:
    "data-[state=active]:bg-[linear-gradient(to_top,_rgba(239,108,60,0.3),_rgba(239,108,60,0))] data-[state=active]:border-[#EF6C3C]",
  cline:
    "data-[state=active]:bg-[linear-gradient(to_top,_rgba(112,128,144,0.3),_rgba(112,128,144,0))] data-[state=active]:border-[#708090]",
  cursor:
    "data-[state=active]:bg-[linear-gradient(to_top,_rgba(255,255,255,0.08),_rgba(255,255,255,0))] data-[state=active]:border-[#708090]",
  roocline:
    "data-[state=active]:bg-[linear-gradient(to_top,_rgba(45,32,92,0.8),_rgba(45,32,92,0))] data-[state=active]:border-[#7E3FF2]",
  windsurf:
    "data-[state=active]:bg-[linear-gradient(to_top,_rgba(0,176,137,0.3),_rgba(0,176,137,0))] data-[state=active]:border-[#00B089]",
  witsy:
    "data-[state=active]:bg-[linear-gradient(to_top,_rgba(33,135,255,0.3),_rgba(33,135,255,0))] data-[state=active]:border-[#2187FF]",
  enconvo:
    "data-[state=active]:bg-[linear-gradient(to_top,_rgba(126,63,242,0.3),_rgba(126,63,242,0))] data-[state=active]:border-[#7E3FF2]",
};

const getColorGradient = (color: string) => {
  if (colorGradientMap[color]) {
    return colorGradientMap[color];
  }
  return "data-[state=active]:bg-[linear-gradient(to_top,_rgba(126,63,242,0.3),_rgba(126,63,242,0))] data-[state=active]:border-[#7E3FF2]";
};

const allTabs = [{ key: "mcp", label: "Link MCP", icon: "🔗" }, ...clientTabs];

async function copyText(text: string): Promise<void> {
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

function CommandBlock({
  label,
  command,
  copyKey,
  copiedKey,
  onCopied,
}: {
  label: string;
  command: string;
  copyKey: string;
  copiedKey: string | null;
  onCopied: (key: string) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs text-zinc-500">{label}</p>
      <div className="relative">
        <pre className="bg-zinc-800 px-4 py-3 pr-14 rounded-md overflow-x-auto text-sm">
          <code className="text-gray-300 whitespace-pre-wrap break-all">{command}</code>
        </pre>
        <button
          type="button"
          className="absolute top-0 right-0 py-3 px-4 rounded-md hover:bg-zinc-600 bg-zinc-700"
          aria-label={`Copiar comando ${label}`}
          onClick={() => {
            copyText(command).then(() => onCopied(copyKey));
          }}
        >
          {copiedKey === copyKey ? (
            <Check className="h-5 w-5 text-green-400" />
          ) : (
            <Copy className="h-5 w-5 text-zinc-400" />
          )}
        </button>
      </div>
    </div>
  );
}

export const Install = () => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
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

  // Token de agente imutável (ADR-008): criado AUTOMATICAMENTE no primeiro
  // acesso (get-or-create idempotente) e exibido permanentemente, embutido nos
  // comandos abaixo.
  const { getOrCreateToken } = useAgentTokenApi();
  const [rawToken, setRawToken] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getOrCreateToken()
      .then((data) => {
        if (!cancelled && data.token) setRawToken(data.token);
      })
      .catch(() => {
        // Sem sessão/erro: página segue com placeholder (fluxo legado intacto).
      });
    return () => {
      cancelled = true;
    };
  }, [getOrCreateToken]);

  useEffect(() => {
    let cancelled = false;
    fetchMcpBaseUrl()
      .then((base) => {
        if (!cancelled) setMcpBase(base);
      })
      .catch(() => {
        // Mantém fallback síncrono (getMcpBaseUrl).
      });
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
    <div>
      <PageHeader
        className="mb-4"
        icon={Plug}
        title={`Instalar ${APP_NAME}`}
        description={APP_TAGLINE}
      />
      <p className="text-sm text-zinc-500 mb-6 max-w-2xl">
        Execute o comando na máquina onde o Claude ou o Cursor está instalado. O
        hostname é resolvido automaticamente pela variável do sistema (
        <code className="text-zinc-400">%COMPUTERNAME%</code> /{" "}
        <code className="text-zinc-400">$env:COMPUTERNAME</code> /{" "}
        <code className="text-zinc-400">$(hostname)</code>) — não use o usuário
        Linux do servidor.{" "}
        {groupLocked ? (
          <>
            Sua conta já está no grupo abaixo — os comandos já incluem{" "}
            <code className="text-zinc-400">?group=</code> para vincular novas
            máquinas na primeira conexão MCP.
          </>
        ) : (
          <>
            Informe o <strong className="text-zinc-400 font-medium">grupo
            (equipe)</strong> abaixo — ele é vinculado ao hostname na{" "}
            <strong className="text-zinc-400 font-medium">primeira conexão MCP</strong>{" "}
            durante a instalação (parâmetro <code className="text-zinc-400">?group=</code>
            na URL). Depois disso, leituras e escritas usam o cadastro do usuário.
          </>
        )}
      </p>

      <div className="mb-6 max-w-md space-y-2">
        <label htmlFor="install-group" className="text-xs text-zinc-500">
          {groupLocked
            ? "Grupo (equipe) — já vinculado à sua conta"
            : "Grupo (equipe) — vinculado na instalação. Vazio usa Default."}
        </label>
        <input
          id="install-group"
          type="text"
          value={effectiveGroup}
          onChange={(e) => setGroup(e.target.value)}
          readOnly={groupLocked}
          aria-readonly={groupLocked}
          placeholder="ex.: Fiscal"
          className={`w-full bg-zinc-800 border border-zinc-700 rounded-md px-3 py-2 text-sm text-gray-300 placeholder:text-zinc-600 focus:outline-none focus:border-primary${groupLocked ? " cursor-default opacity-90" : ""}`}
        />
      </div>

      {rawToken && (
        <div
          data-testid="token-banner"
          className="mb-6 space-y-3 rounded-md border border-zinc-700 bg-zinc-900 p-4"
        >
          <p className="text-sm text-zinc-300">
            <strong>Seu token de agente</strong> (fixo da sua conta) — já
            embutido nos comandos abaixo. É ele que identifica{" "}
            <em>você</em> nas leituras e gravações; use o mesmo token em todas
            as suas máquinas.
          </p>
          <div className="relative">
            <pre className="bg-zinc-800 px-4 py-3 pr-14 rounded-md overflow-x-auto text-sm">
              <code data-testid="raw-token" className="text-gray-300 break-all">
                {rawToken}
              </code>
            </pre>
            <button
              type="button"
              className="absolute top-0 right-0 py-3 px-4 rounded-md hover:bg-zinc-600 bg-zinc-700"
              aria-label="Copiar token"
              onClick={() => copyText(rawToken).then(() => markCopied("raw-token"))}
            >
              {copiedKey === "raw-token" ? (
                <Check className="h-5 w-5 text-green-400" />
              ) : (
                <Copy className="h-5 w-5 text-zinc-400" />
              )}
            </button>
          </div>
        </div>
      )}

      <div className="hidden">
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(239,108,60,0.3),_rgba(239,108,60,0))] data-[state=active]:border-[#EF6C3C]"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(112,128,144,0.3),_rgba(112,128,144,0))] data-[state=active]:border-[#708090]"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(45,32,92,0.3),_rgba(45,32,92,0))] data-[state=active]:border-[#2D205C]"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(0,176,137,0.3),_rgba(0,176,137,0))] data-[state=active]:border-[#00B089]"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(33,135,255,0.3),_rgba(33,135,255,0))] data-[state=active]:border-[#2187FF]"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(126,63,242,0.3),_rgba(126,63,242,0))] data-[state=active]:border-[#7E3FF2]"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(239,108,60,0.3),_rgba(239,108,60,0))] data-[state=active]:border-[#EF6C3C]"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(107,33,168,0.3),_rgba(107,33,168,0))] data-[state=active]:border-primary"></div>
        <div className="data-[state=active]:bg-[linear-gradient(to_top,_rgba(255,255,255,0.08),_rgba(255,255,255,0))] data-[state=active]:border-[#708090]"></div>
      </div>

      <Tabs defaultValue="claude" className="w-full">
        <TabsList className="bg-transparent border-b border-zinc-800 rounded-none w-full justify-start gap-0 p-0 grid grid-cols-3">
          {allTabs.map(({ key, label, icon }) => (
            <TabsTrigger
              key={key}
              value={key}
              className={`flex-1 px-0 pb-2 rounded-none ${getColorGradient(
                key,
              )} data-[state=active]:border-b-2 data-[state=active]:shadow-none text-zinc-400 data-[state=active]:text-white flex items-center justify-center gap-2 text-sm`}
            >
              {icon.startsWith("/") ? (
                <div>
                  <div className="w-6 h-6 rounded-full bg-zinc-700 flex items-center justify-center overflow-hidden">
                    <Image src={icon} alt={label} width={40} height={40} />
                  </div>
                </div>
              ) : (
                <div className="h-6">
                  <span className="relative top-1">{icon}</span>
                </div>
              )}
              <span>{label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="mcp" className="mt-6">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="py-4">
              <CardTitle className="text-white text-xl">Link MCP</CardTitle>
            </CardHeader>
            <hr className="border-zinc-800" />
            <CardContent className="py-4 space-y-4">
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
            </CardContent>
          </Card>
        </TabsContent>

        {clientTabs.map(({ key }) => (
          <TabsContent key={key} value={key} className="mt-6">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader className="py-4">
                <CardTitle className="text-white text-xl">
                  {key === "claude"
                    ? "Instalação — Claude"
                    : `Comando de instalação — ${key.charAt(0).toUpperCase() + key.slice(1)}`}
                </CardTitle>
                {key === "claude" && (
                  <p className="text-sm text-zinc-500 mt-1">
                    Execute os passos na ordem, na máquina onde o Claude está instalado.
                  </p>
                )}
              </CardHeader>
              <hr className="border-zinc-800" />
              <CardContent className="py-4 space-y-8">
                {key === "claude"
                  ? installShellVariants.map((variant) => (
                      <div key={`${key}-${variant.id}`} className="space-y-4">
                        <h3 className="text-sm font-medium text-zinc-300">{variant.label}</h3>
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
              </CardContent>
            </Card>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
};

export default Install;
