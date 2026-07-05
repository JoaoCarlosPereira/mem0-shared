"use client";

/**
 * Login Google via redirect OAuth (ADR-002).
 * Requer a UI publicada em hostname+HTTPS com redirect cadastrado no Google.
 * O backend valida o domínio corporativo (403 fora dele).
 */
import { Suspense } from "react";
import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { APP_NAME } from "@/lib/branding";

const REDIRECT_ERROR_MESSAGES: Record<string, string> = {
  AccessDenied:
    "Acesso restrito a contas Google do domínio da empresa. Use sua conta corporativa.",
  Configuration:
    "Login com Google indisponível no momento. Verifique a configuração ou fale com quem administra a stack.",
  Default: "Não foi possível concluir o login. Tente novamente.",
};

function LoginContent() {
  const searchParams = useSearchParams();
  const redirectError = searchParams.get("error");
  const error = redirectError
    ? REDIRECT_ERROR_MESSAGES[redirectError] ?? REDIRECT_ERROR_MESSAGES.Default
    : null;

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
          <Button
            className="w-full"
            onClick={() => signIn("google", { redirectTo: "/" })}
          >
            Entrar com Google
          </Button>
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
