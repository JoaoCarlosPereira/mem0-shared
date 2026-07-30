"use client";

import { Suspense, useEffect, useState } from "react";
import { signIn } from "next-auth/react";
import { useSearchParams, useRouter } from "next/navigation";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";
import { isLegacyAuthUi, isAuthUiRequired } from "@/lib/auth-ui-mode";

const REDIRECT_ERROR_MESSAGES: Record<string, string> = {
  AccessDenied:
    "Acesso restrito a contas Google do domínio da empresa. Use sua conta corporativa.",
  Configuration:
    "Login com Google indisponível no momento. Verifique a configuração ou fale com quem administra a stack.",
  SessionExpired:
    "Sua sessão expirou ou ficou inválida. Entre novamente com sua conta Google.",
  Default: "Não foi possível concluir o login. Tente novamente.",
};

function envGoogleConfigured(): boolean {
  return Boolean(
    (
      process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ||
      process.env.GOOGLE_CLIENT_ID ||
      ""
    ).trim() &&
      // Placeholder still unreplaced by entrypoint → treat as missing.
      process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID !== "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
  );
}

function LoginContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const redirectError = searchParams.get("error");
  const error = redirectError
    ? REDIRECT_ERROR_MESSAGES[redirectError] ?? REDIRECT_ERROR_MESSAGES.Default
    : null;
  // Runtime check: NextAuth providers are server-configured even when the
  // client bundle lost NEXT_PUBLIC_* during an image rebuild without placeholders.
  const [providerGoogle, setProviderGoogle] = useState<boolean | null>(null);
  useEffect(() => {
    let cancelled = false;
    fetch("/api/auth/providers")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled) setProviderGoogle(Boolean(data?.google));
      })
      .catch(() => {
        if (!cancelled) setProviderGoogle(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const googleAvailable =
    isAuthUiRequired() || envGoogleConfigured() || providerGoogle === true;
  // Only show legacy LAN skip when Google is confirmed unavailable (or still loading
  // with no env signal). Prefer Google button whenever the provider exists.
  const legacy =
    providerGoogle === false && isLegacyAuthUi() && !envGoogleConfigured();
  const showGoogle =
    googleAvailable || (providerGoogle === null && !isLegacyAuthUi());

  return (
    <div className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-slate-950/95 backdrop-blur-sm">
      <div className="glass mx-4 w-full max-w-md rounded-3xl border border-slate-700/50 p-8 shadow-2xl md:p-10">
        <div className="mb-8 flex flex-col items-center">
          <div className="mb-4 rounded-2xl bg-blue-600 p-4 shadow-xl shadow-blue-500/20">
            <Image src="/logo.svg" alt={APP_NAME} width={32} height={32} />
          </div>
          <h1 className="text-xl font-bold text-white">{APP_NAME}</h1>
          <p className="mt-1 text-ui-caption font-black uppercase tracking-widest text-slate-500">
            {APP_TAGLINE}
          </p>
        </div>

        <div className="flex flex-col gap-4">
          {error && (
            <p
              id="login-error"
              role="alert"
              className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3 text-center text-ui-body-sm font-bold uppercase text-rose-400"
            >
              {error}
            </p>
          )}
          {legacy && (
            <p className="text-center text-sm text-slate-400">
              Login Google desabilitado neste ambiente (modo legado LAN).
            </p>
          )}
          {showGoogle && (
            <Button
              className="min-h-11 w-full rounded-xl py-6 text-sm font-black uppercase tracking-widest shadow-xl shadow-blue-600/20"
              onClick={() => signIn("google", { redirectTo: "/" })}
            >
              Entrar com Google
            </Button>
          )}
          {legacy && (
            <Button
              className="min-h-11 w-full rounded-xl py-6 text-sm font-black uppercase tracking-widest"
              variant="secondary"
              onClick={() => router.push("/")}
            >
              Continuar sem login
            </Button>
          )}
        </div>
      </div>
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
