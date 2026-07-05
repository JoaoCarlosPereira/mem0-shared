"use client";

/**
 * Wizard de primeiro login (feature auth Google, task_08).
 *
 * Coleta a máquina atual e o grupo/equipe, propõe o vínculo com o usuário
 * legado e confirma o resultado ("Encontramos N memórias..."). Conflito (409)
 * é terminal: fica registrado para tratamento — sem opção de forçar.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useSelector } from "react-redux";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useGroupsApi, type Group } from "@/hooks/useGroupsApi";
import {
  useOnboardingApi,
  type MachineSuggestions,
} from "@/hooks/useOnboardingApi";
import type { RootState } from "@/store/store";

const NEW_GROUP_VALUE = "__novo__";

export default function OnboardingPage() {
  const router = useRouter();
  const { data: session, status, update } = useSession();
  const person = useSelector((state: RootState) => state.profile.person);
  const { fetchGroups } = useGroupsApi();
  const { submitOnboarding, fetchMachineSuggestions } = useOnboardingApi();

  const [groups, setGroups] = useState<Group[]>([]);
  const [hostname, setHostname] = useState("");
  const [suggestions, setSuggestions] = useState<MachineSuggestions | null>(null);
  const [selectedGroup, setSelectedGroup] = useState("");
  const [newGroupName, setNewGroupName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);

  // Usuário já vinculado que acessa diretamente volta ao painel.
  useEffect(() => {
    if (
      status === "authenticated" &&
      session?.firstLogin !== true &&
      person?.machineHostname
    ) {
      router.replace("/");
    }
  }, [status, session, person, router]);

  useEffect(() => {
    fetchGroups()
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [fetchGroups]);

  // Sugestão automática da máquina: DNS reverso do IP do navegador (quando a
  // LAN resolve) + lista de máquinas legadas ainda sem dono (autocomplete).
  useEffect(() => {
    fetchMachineSuggestions()
      .then((data) => {
        setSuggestions(data);
        if (data.detected_hostname) {
          setHostname((current) => current || data.detected_hostname!);
        }
      })
      .catch(() => setSuggestions(null));
  }, [fetchMachineSuggestions]);

  const groupNameToSend =
    selectedGroup === NEW_GROUP_VALUE ? newGroupName.trim() : selectedGroup;

  const canSubmit =
    hostname.trim().length > 0 &&
    (selectedGroup !== NEW_GROUP_VALUE || newGroupName.trim().length > 0) &&
    !submitting;

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      await submitOnboarding(hostname.trim(), groupNameToSend || null);
      // Limpa o flag de onboarding na sessão e vai direto ao painel de instalação.
      await update({ firstLogin: false });
      window.location.assign("/");
    } catch (err: any) {
      if (err?.response?.status === 409) {
        setConflict(true);
      } else {
        setError(
          err?.response?.data?.detail ??
            "Não foi possível concluir o vínculo. Tente novamente.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (conflict) {
    return (
      <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
        <Card className="w-full max-w-lg border-zinc-800 bg-zinc-900">
          <CardHeader>
            <CardTitle>Máquina em conflito</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-zinc-300">
            <p role="alert">
              Esta máquina já está vinculada a outra conta Google. O conflito
              foi registrado e precisa de tratamento administrativo — nenhum
              vínculo automático foi feito.
            </p>
            <Button variant="outline" onClick={() => router.push("/")}>
              Ir para o painel
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
      <Card className="w-full max-w-lg border-zinc-800 bg-zinc-900">
        <CardHeader>
          <CardTitle>Bem-vindo! Vamos configurar sua conta</CardTitle>
          <CardDescription>
            Informe a máquina que você usa hoje e sua equipe. Se a máquina já
            gravou memórias, elas serão vinculadas à sua conta.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {error && (
            <p
              role="alert"
              className="rounded-md border border-red-900 bg-red-950/50 p-3 text-sm text-red-300"
            >
              {error}
            </p>
          )}
          <div className="space-y-2">
            <Label htmlFor="hostname">Nome da máquina atual</Label>
            <Input
              id="hostname"
              placeholder="ex.: S0293, DESKTOP-JOAO"
              value={hostname}
              onChange={(e) => setHostname(e.target.value)}
              list="known-machines"
            />
            <datalist id="known-machines">
              {(suggestions?.unlinked_hostnames ?? []).map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
            {suggestions?.detected_hostname &&
            hostname === suggestions.detected_hostname ? (
              <p className="text-xs text-zinc-500" data-testid="detected-hint">
                Detectamos <strong>{suggestions.detected_hostname}</strong> pela
                rede — confira se é o seu computador antes de continuar.
              </p>
            ) : (
              <p className="text-xs text-zinc-500">
                É o hostname do seu computador — o mesmo usado pelos agentes até
                hoje.
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="group">Grupo / equipe</Label>
            <select
              id="group"
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 p-2 text-sm"
              value={selectedGroup}
              onChange={(e) => setSelectedGroup(e.target.value)}
            >
              <option value="">Default</option>
              {groups.map((group) => (
                <option key={group.id} value={group.name}>
                  {group.name}
                </option>
              ))}
              <option value={NEW_GROUP_VALUE}>+ Criar novo grupo…</option>
            </select>
            {selectedGroup === NEW_GROUP_VALUE && (
              <Input
                aria-label="Nome do novo grupo"
                placeholder="Nome do novo grupo"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
              />
            )}
          </div>
          <Button className="w-full" disabled={!canSubmit} onClick={handleSubmit}>
            {submitting ? "Vinculando…" : "Vincular máquina e continuar"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
