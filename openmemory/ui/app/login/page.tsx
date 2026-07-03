"use client";

/**
 * Login Google — dois caminhos coexistem (ADR-002 + ADR-007):
 *
 * 1. Redirect (primário): requer a UI publicada em hostname+HTTPS
 *    (https://memorias.sysmo.com.br) com redirect cadastrado no Google.
 * 2. Device flow (alternativa): código digitado em google.com/device —
 *    funciona até em IP interno/HTTP e serve de fallback se o redirect
 *    estiver indisponível/mal configurado.
 *
 * Nos dois casos o backend valida o domínio corporativo (403 fora dele).
 */
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getApiUrl } from "@/lib/api-url";
import { APP_NAME } from "@/lib/branding";

const REDIRECT_ERROR_MESSAGES: Record<string, string> = {
  AccessDenied:
    "Acesso restrito a contas Google do domínio da empresa. Use sua conta corporativa.",
  Configuration:
    "Login com redirect indisponível — use a opção 'Entrar com código' abaixo.",
  Default: "Não foi possível concluir o login. Tente novamente ou use o código.",
};

interface DeviceInfo {
  device_code: string;
  user_code: string;
  verification_url: string;
  interval: number;
}

function LoginContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectError = searchParams.get("error");

  const [device, setDevice] = useState<DeviceInfo | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(
    redirectError
      ? REDIRECT_ERROR_MESSAGES[redirectError] ?? REDIRECT_ERROR_MESSAGES.Default
      : null,
  );
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollTimer.current) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  async function startDeviceLogin() {
    setStarting(true);
    setError(null);
    try {
      const resp = await axios.post(`${getApiUrl()}/api/v1/auth/google/device/start`);
      setDevice(resp.data);
    } catch (err: any) {
      setError(
        err?.response?.status === 503
          ? "Login Google não configurado no servidor — fale com quem administra a stack."
          : "Não foi possível iniciar o login. Tente novamente.",
      );
    } finally {
      setStarting(false);
    }
  }

  const poll = useCallback(async () => {
    if (!device) return;
    try {
      const resp = await axios.post(`${getApiUrl()}/api/v1/auth/google/device/poll`, {
        device_code: device.device_code,
      });
      if (resp.data.status !== "ok") return; // pending/slow_down: segue aguardando
      stopPolling();
      await signIn("device", {
        apiToken: resp.data.access_token,
        redirect: false,
      });
      router.push(resp.data.first_login ? "/onboarding" : "/");
      router.refresh();
    } catch (err: any) {
      const status = err?.response?.status;
      if (status === 403) {
        stopPolling();
        setDevice(null);
        setError(
          "Acesso restrito a contas Google do domínio da empresa. Use sua conta corporativa.",
        );
      } else if (status === 410) {
        stopPolling();
        setDevice(null);
        setError("O código expirou. Inicie o login novamente.");
      }
      // Outros erros (rede momentânea): mantém o polling.
    }
  }, [device, router, stopPolling]);

  useEffect(() => {
    if (!device) return;
    const everyMs = Math.max(device.interval, 3) * 1000;
    pollTimer.current = setInterval(poll, everyMs);
    return stopPolling;
  }, [device, poll, stopPolling]);

  return (
    <div className="flex min-h-[calc(100vh-64px)] items-center justify-center px-4">
      <Card className="w-full max-w-md border-zinc-800 bg-zinc-900">
        <CardHeader className="items-center text-center">
          <Image src="/logo.svg" alt={APP_NAME} width={48} height={48} />
          <CardTitle className="mt-2 text-2xl">{APP_NAME}</CardTitle>
          <CardDescription>
            Entre com sua conta Google corporativa para acessar a rede de
            memórias.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {error && (
            <p
              role="alert"
              className="rounded-md border border-red-900 bg-red-950/50 p-3 text-sm text-red-300"
            >
              {error}
            </p>
          )}
          {device ? (
            <div className="space-y-4 text-center" data-testid="device-instructions">
              <p className="text-sm text-zinc-300">
                Acesse{" "}
                <a
                  href={device.verification_url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-medium text-blue-400 underline"
                >
                  {device.verification_url.replace(/^https?:\/\//, "")}
                </a>{" "}
                em qualquer navegador (pode ser no celular) e digite o código:
              </p>
              <p
                data-testid="user-code"
                className="rounded-md border border-zinc-700 bg-zinc-950 py-3 text-2xl font-bold tracking-widest"
              >
                {device.user_code}
              </p>
              <p className="text-xs text-zinc-500">
                Aguardando a autorização… esta página conclui o login sozinha.
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  stopPolling();
                  setDevice(null);
                }}
              >
                Cancelar
              </Button>
            </div>
          ) : (
            <>
              <Button
                className="w-full"
                onClick={() => signIn("google", { redirectTo: "/" })}
              >
                Entrar com Google
              </Button>
              <Button
                variant="outline"
                className="w-full"
                disabled={starting}
                onClick={startDeviceLogin}
              >
                {starting
                  ? "Gerando código…"
                  : "Entrar com código (sem redirect)"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginContent />
    </Suspense>
  );
}
