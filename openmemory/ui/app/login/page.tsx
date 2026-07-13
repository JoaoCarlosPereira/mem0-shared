"use client";

import { Suspense } from "react";
import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import { APP_NAME, APP_TAGLINE } from "@/lib/branding";

const REDIRECT_ERROR_MESSAGES: Record<string, string> = {
  AccessDenied:
    "Acesso restrito a contas Google do domínio da empresa. Use sua conta corporativa.",
  Configuration:
    "Login com Google indisponível no momento. Verifique a configuração ou fale com quem administra a stack.",
  SessionExpired:
    "Sua sessão expirou ou ficou inválida. Entre novamente com sua conta Google.",
  Default: "Não foi possível concluir o login. Tente novamente.",
};

function LoginContent() {
  const searchParams = useSearchParams();
  const redirectError = searchParams.get("error");
  const error = redirectError
    ? REDIRECT_ERROR_MESSAGES[redirectError] ?? REDIRECT_ERROR_MESSAGES.Default
    : null;

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
          <Button
            className="min-h-11 w-full rounded-xl py-6 text-sm font-black uppercase tracking-widest shadow-xl shadow-blue-600/20"
            onClick={() => signIn("google", { redirectTo: "/" })}
          >
            Entrar com Google
          </Button>
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
