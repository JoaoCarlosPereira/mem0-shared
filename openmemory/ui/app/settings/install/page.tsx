"use client";

/**
 * Consulta do token de agente (ADR-008: imutável e permanentemente exibível).
 *
 * O token é criado automaticamente na primeira visita à tela de instalação
 * (dashboard) e nunca muda; esta página é uma visão de consulta/cópia. Em
 * emergência (vazamento), a revogação é administrativa — direto no banco.
 */
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { useImmutableAgentToken } from "@/hooks/useImmutableAgentToken";

export default function AgentTokenPage() {
  const { tokenInfo, error, loading } = useImmutableAgentToken();
  const { toast } = useToast();

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Seu token de agente</h1>
        <p className="text-sm text-zinc-400">
          Token fixo da sua conta — identifica você nas leituras e gravações
          dos agentes. Use o mesmo valor em todas as suas máquinas.
        </p>
      </div>

      <Card className="border-zinc-800 bg-zinc-900">
        <CardHeader>
          <CardTitle>Token</CardTitle>
          <CardDescription>
            Criado automaticamente no primeiro acesso; imutável.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? (
            <p role="alert" className="text-sm text-red-300">
              Não foi possível carregar o token. Recarregue a página.
            </p>
          ) : loading ? (
            <p className="text-sm text-zinc-400">Carregando…</p>
          ) : !tokenInfo ? (
            <p className="text-sm text-zinc-400">
              Faça login para ver seu token de agente.
            </p>
          ) : (
            <div className="space-y-3" data-testid="token-block">
              <div className="flex items-center gap-2">
                <code
                  data-testid="raw-token"
                  className="flex-1 overflow-x-auto rounded-md border border-zinc-700 bg-zinc-950 p-3 text-sm"
                >
                  {tokenInfo.token}
                </code>
                <Button
                  variant="outline"
                  size="sm"
                  aria-label="Copiar token"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(tokenInfo.token ?? "");
                      toast({ title: "Token copiado" });
                    } catch {
                      toast({
                        title: "Não foi possível copiar",
                        variant: "destructive",
                      });
                    }
                  }}
                >
                  Copiar
                </Button>
              </div>
              <p className="text-xs text-zinc-500">
                Criado em: {tokenInfo.created_at ?? "—"}
                {tokenInfo.last_used_at
                  ? ` · Último uso: ${tokenInfo.last_used_at}`
                  : ""}
              </p>
              <p className="text-sm text-zinc-400">
                Os comandos de instalação com este token já preenchido estão na{" "}
                <Link href="/" className="text-blue-400 underline">
                  tela inicial (Instalar)
                </Link>
                .
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
