"use client";

/**
 * Wizard de primeiro login (feature auth Google, task_08).
 *
 * Coleta a máquina atual e o grupo/equipe, propõe o vínculo com o usuário
 * legado e confirma o resultado.
 */
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { useSelector } from "react-redux";
import axios from "axios";
import { Loader2 } from "lucide-react";

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
import { useApiSessionReady } from "@/hooks/useApiSessionReady";
import {
  isValidSysmoHostname,
  normalizeSysmoHostname,
  SYSMO_HOSTNAME_ERROR,
  SYSMO_HOSTNAME_HINT,
} from "@/lib/hostname-validation";
import { setApiAccessToken } from "@/lib/api-client";
import { getApiUrl } from "@/lib/api-url";
import type { RootState } from "@/store/store";

const NEW_GROUP_VALUE = "__novo__";
const SESSION_EXPIRED_LOGIN = "/login?error=SessionExpired";

export default function OnboardingPage() {
  const router = useRouter();
  const { data: session, status, update } = useSession();
  const apiSessionReady = useApiSessionReady();
  const person = useSelector((state: RootState) => state.profile.person);
  const { fetchGroups } = useGroupsApi();
  const { submitOnboarding, fetchMachineSuggestions } = useOnboardingApi();

  const [groups, setGroups] = useState<Group[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [groupsError, setGroupsError] = useState(false);

  const [hostname, setHostname] = useState("");
  const [suggestions, setSuggestions] = useState<MachineSuggestions | null>(null);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionsError, setSuggestionsError] = useState(false);

  const [selectedGroup, setSelectedGroup] = useState("");
  const [newGroupName, setNewGroupName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submittingStatusText, setSubmittingStatusText] = useState<string | null>(null);
  const [showSessionRecoveryFallback, setShowSessionRecoveryFallback] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [errorType, setErrorType] = useState<"validation" | "server" | "auth" | null>(null);
  const [conflict, setConflict] = useState(false);
  const [hostnameError, setHostnameError] = useState<string | null>(null);

  // Confirmação de hostname divergente (BE-4)
  const [showMismatchConfirm, setShowMismatchConfirm] = useState(false);

  const normalizedHostname = normalizeSysmoHostname(hostname);
  const hostnameValid = normalizedHostname !== null;

  // Usuário já vinculado que acessa diretamente volta ao painel.
  useEffect(() => {
    if (
      status === "authenticated" &&
      (session as { firstLogin?: boolean } | null)?.firstLogin !== true &&
      person?.machineHostname
    ) {
      router.replace("/");
    }
  }, [status, session, person, router]);

  const loadGroups = useCallback((signal?: AbortSignal) => {
    setGroupsLoading(true);
    setGroupsError(false);
    fetchGroups()
      .then((data) => {
        if (signal?.aborted) return;
        setGroups(data || []);
        setGroupsLoading(false);
      })
      .catch((err) => {
        if (signal?.aborted || axios.isCancel(err)) return;
        setGroups([]);
        setGroupsLoading(false);
        setGroupsError(true);
      });
  }, [fetchGroups]);

  const loadSuggestions = useCallback((signal?: AbortSignal) => {
    setSuggestionsLoading(true);
    setSuggestionsError(false);
    fetchMachineSuggestions(signal)
      .then((data) => {
        if (signal?.aborted) return;
        setSuggestions(data);
        setSuggestionsLoading(false);
        if (data?.detected_hostname && isValidSysmoHostname(data.detected_hostname)) {
          setHostname((current) => current || normalizeSysmoHostname(data.detected_hostname!)!);
        }
        if (data?.suggested_group) {
          setSelectedGroup((current) => current || data.suggested_group!);
        }
      })
      .catch((err) => {
        if (signal?.aborted || axios.isCancel(err)) return;
        setSuggestions(null);
        setSuggestionsLoading(false);
        setSuggestionsError(true);
      });
  }, [fetchMachineSuggestions]);

  // UI-1 + UI-9: Esperar sessão autenticada E apiSessionReady antes dos fetches com AbortController
  useEffect(() => {
    if (status !== "authenticated" || !apiSessionReady) {
      return;
    }
    const abortController = new AbortController();
    loadGroups(abortController.signal);
    loadSuggestions(abortController.signal);

    return () => {
      abortController.abort();
    };
  }, [status, apiSessionReady, loadGroups, loadSuggestions]);

  const groupNameToSend =
    selectedGroup === NEW_GROUP_VALUE ? newGroupName.trim() : selectedGroup;

  const groupReady =
    selectedGroup === NEW_GROUP_VALUE
      ? newGroupName.trim().length > 0
      : selectedGroup.length > 0;

  const canSubmit = hostnameValid && groupReady && !submitting && !groupsLoading;

  const handleLogout = useCallback(() => {
    setApiAccessToken(null);
    void signOut({ callbackUrl: "/login" });
  }, []);

  const handleSessionExpired = useCallback(() => {
    setApiAccessToken(null);
    void signOut({ callbackUrl: SESSION_EXPIRED_LOGIN });
  }, []);

  const executeSubmit = async (machine: string) => {
    setSubmitting(true);
    setError(null);
    setErrorType(null);
    setHostnameError(null);
    setSubmittingStatusText(null);
    setShowSessionRecoveryFallback(false);

    try {
      await submitOnboarding(machine, groupNameToSend || null);
    } catch (err: any) {
      setSubmitting(false);
      if (axios.isAxiosError(err)) {
        const statusCode = err.response?.status;
        if (statusCode === 409) {
          setConflict(true);
          return;
        } else if (statusCode === 401) {
          setErrorType("auth");
          setError("Sua sessão expirou. Por favor, faça login novamente.");
          return;
        } else if (statusCode === 400 || statusCode === 422) {
          setErrorType("validation");
          setError(
            err.response?.data?.detail ??
              "Dados inválidos para o vínculo da máquina. Verifique os campos informados."
          );
          return;
        } else {
          setErrorType("server");
          setError(
            err.response?.data?.detail ??
              "Ocorreu um erro no servidor ao processar o vínculo. Tente novamente."
          );
          return;
        }
      }
      setErrorType("server");
      setError("Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.");
      return;
    }

    // BE-5: Separação de POST e update da sessão
    setSubmittingStatusText("Vínculo concluído, atualizando sessão…");

    let updateSuccess = false;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        await update({ firstLogin: false });
        updateSuccess = true;
        break;
      } catch {
        // Retry imediato sem delay síncrono prolongado
      }
    }

    if (updateSuccess) {
      window.location.assign("/");
      return;
    }

    // Se o update falhar persistentemente, verificar via /api/v1/auth/me se o vínculo existe
    try {
      const meResp = await axios.get(`${getApiUrl()}/api/v1/auth/me`);
      if (meResp.data?.machine?.hostname) {
        // Máquina vinculada com sucesso no backend
        setShowSessionRecoveryFallback(true);
        setSubmitting(false);
        return;
      }
    } catch {
      // Ignora erro do /auth/me fallback
    }

    setSubmitting(false);
    setErrorType("server");
    setError("O vínculo foi realizado, mas não conseguimos atualizar a sessão local automaticamente. Tente recarregar a página.");
  };

  const handleSubmit = async () => {
    const machine = normalizeSysmoHostname(hostname);
    if (!machine) {
      setHostnameError(SYSMO_HOSTNAME_ERROR);
      return;
    }

    // BE-4: Confirmação de hostname divergente (comparação normalizada case-insensitive)
    const detectedNorm = suggestions?.detected_hostname
      ? normalizeSysmoHostname(suggestions.detected_hostname)
      : null;

    if (detectedNorm && machine !== detectedNorm) {
      setShowMismatchConfirm(true);
      return;
    }

    await executeSubmit(machine);
  };

  // Tela de loading inicial enquanto aguarda status de autenticação ou apiSessionReady
  if (status === "loading" || !apiSessionReady) {
    return (
      <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
        <Card className="w-full max-w-lg border-zinc-800 bg-zinc-900">
          <CardContent className="flex flex-col items-center justify-center py-12 text-center text-zinc-400">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500 mb-4" />
            <p className="text-sm font-medium">Preparando ambiente de primeiro acesso…</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // UI-3: Tela de conflito 409 sem loop
  if (conflict) {
    return (
      <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
        <Card className="w-full max-w-lg border-zinc-800 bg-zinc-900">
          <CardHeader>
            <CardTitle>Máquina em conflito</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-zinc-300">
            <p role="alert">
              Esta máquina já está vinculada a outra conta Google. O conflito
              foi registrado e precisa de tratamento administrativo — nenhum
              vínculo automático foi feito.
            </p>
            <p className="text-xs text-zinc-400">
              Se esta máquina é realmente sua, entre em contato com o administrador do sistema para liberar o vínculo.
            </p>
            <div className="flex flex-col sm:flex-row gap-2 pt-2">
              <Button
                variant="default"
                onClick={() => {
                  setConflict(false);
                  setHostname("");
                  setError(null);
                  setErrorType(null);
                }}
              >
                Voltar e informar outra máquina
              </Button>
              <Button variant="outline" onClick={handleLogout}>
                Sair e entrar com outra conta
              </Button>
            </div>
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
            Informe o <strong>nome da máquina</strong> que você usa hoje e sua
            equipe. Se a máquina já gravou memórias, elas serão vinculadas à sua
            conta.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {error && (
            <div
              role="alert"
              className="rounded-md border border-red-900 bg-red-950/50 p-3 text-sm text-red-300 space-y-2"
            >
              <p>{error}</p>
              {errorType === "auth" && (
                <Button size="sm" variant="outline" onClick={handleSessionExpired} className="mt-1">
                  Fazer login novamente
                </Button>
              )}
              {errorType === "server" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="mt-1"
                >
                  Tentar novamente
                </Button>
              )}
            </div>
          )}

          {showSessionRecoveryFallback && (
            <div className="rounded-md border border-amber-800 bg-amber-950/40 p-3 text-sm text-amber-300 space-y-2">
              <p>
                Sua máquina foi vinculada com sucesso no servidor! Clique abaixo para prosseguir ao painel.
              </p>
              <Button
                size="sm"
                onClick={() => {
                  window.location.assign("/");
                }}
              >
                Continuar para o painel
              </Button>
            </div>
          )}

          {showMismatchConfirm ? (
            <div
              data-testid="mismatch-confirm-box"
              className="rounded-md border border-amber-800 bg-amber-950/40 p-4 space-y-3 text-sm text-amber-200"
            >
              <p className="font-semibold">Confirmação de máquina</p>
              <p>
                Detectamos <strong>{suggestions?.detected_hostname}</strong> na sua rede, mas você informou <strong>{normalizeSysmoHostname(hostname)}</strong>. Continuar mesmo assim?
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={async () => {
                    setShowMismatchConfirm(false);
                    const machine = normalizeSysmoHostname(hostname);
                    if (machine) {
                      await executeSubmit(machine);
                    }
                  }}
                >
                  Continuar
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowMismatchConfirm(false)}
                >
                  Corrigir
                </Button>
              </div>
            </div>
          ) : null}

          <div className="space-y-2">
            <Label htmlFor="hostname">Nome da máquina atual</Label>
            <p className="text-xs text-zinc-400">
              Informe <strong>apenas o nome/código da máquina</strong> (ex.:
              S0281). Não digite seu nome nem o nome da equipe aqui.
            </p>
            <Input
              id="hostname"
              placeholder="ex.: S0281"
              value={hostname}
              onChange={(e) => {
                setHostname(e.target.value);
                setHostnameError(null);
              }}
              onBlur={() => {
                if (hostname.trim() && !isValidSysmoHostname(hostname)) {
                  setHostnameError(SYSMO_HOSTNAME_ERROR);
                }
              }}
              list="known-machines"
              aria-invalid={hostnameError ? true : undefined}
              className={hostnameError ? "border-red-700" : undefined}
            />
            <datalist id="known-machines">
              {(suggestions?.unlinked_hostnames ?? [])
                .filter((name) => isValidSysmoHostname(name))
                .map((name) => (
                  <option key={name} value={name} />
                ))}
            </datalist>

            {suggestionsLoading && (
              <p className="text-xs text-zinc-500 flex items-center gap-1.5">
                <Loader2 className="h-3 w-3 animate-spin" /> Buscando sugestões de máquina…
              </p>
            )}

            {suggestionsError && (
              <div className="text-xs text-zinc-400 flex items-center justify-between">
                <span>Sugestão de máquina indisponível.</span>
                <button
                  type="button"
                  className="text-blue-400 hover:underline"
                  onClick={() => loadSuggestions()}
                >
                  Tentar novamente
                </button>
              </div>
            )}

            {hostnameError ? (
              <p role="alert" className="text-xs text-red-400">
                {hostnameError}
              </p>
            ) : suggestions?.detected_hostname &&
              hostname === suggestions.detected_hostname ? (
              <p className="text-xs text-zinc-500" data-testid="detected-hint">
                Detectamos <strong>{suggestions.detected_hostname}</strong> pela
                rede — confira se é o seu computador antes de continuar.
              </p>
            ) : (
              <p className="text-xs text-zinc-500">{SYSMO_HOSTNAME_HINT}</p>
            )}
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="group">Grupo / equipe</Label>
              {groupsLoading && (
                <span className="text-xs text-zinc-500 flex items-center gap-1">
                  <Loader2 className="h-3 w-3 animate-spin" /> carregando…
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400">
              Selecione a equipe à qual você pertence. Evite deixar em
              &quot;Default&quot; — isso isola suas memórias das demais equipes.
            </p>

            {groupsError ? (
              <div className="rounded-md border border-zinc-800 bg-zinc-950 p-2.5 text-xs text-zinc-400 flex items-center justify-between">
                <span>Lista de equipes indisponível.</span>
                <Button
                  size="sm"
                  variant="outline"
                  type="button"
                  onClick={() => loadGroups()}
                >
                  Tentar novamente
                </Button>
              </div>
            ) : (
              <select
                id="group"
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 p-2 text-sm"
                value={selectedGroup}
                onChange={(e) => setSelectedGroup(e.target.value)}
                disabled={groupsLoading}
              >
                <option value="">
                  {groupsLoading
                    ? "Carregando equipes…"
                    : groups.length === 0
                    ? "Nenhuma equipe cadastrada (crie uma abaixo)"
                    : "Selecione sua equipe…"}
                </option>
                {groups.map((group) => (
                  <option key={group.id} value={group.name}>
                    {group.name}
                  </option>
                ))}
                <option value={NEW_GROUP_VALUE}>+ Criar novo grupo…</option>
              </select>
            )}

            {selectedGroup === NEW_GROUP_VALUE && (
              <Input
                aria-label="Nome do novo grupo"
                placeholder="Nome do novo grupo"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.target.value)}
              />
            )}
          </div>

          <Button
            className="w-full"
            disabled={!canSubmit}
            onClick={handleSubmit}
          >
            {submitting ? (
              <span className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                {submittingStatusText || "Vinculando…"}
              </span>
            ) : (
              "Vincular máquina e continuar"
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
