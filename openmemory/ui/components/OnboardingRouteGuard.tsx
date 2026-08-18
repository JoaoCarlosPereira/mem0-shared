"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Loader2 } from "lucide-react";
import { isBareRoute } from "@/lib/shell-nav";

/**
 * Guard client-side leve (UI-2) para evitar o flash do dashboard
 * antes de o middleware ou a sessão redirecionar para /onboarding.
 */
export function OnboardingRouteGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, status } = useSession();

  const isBare = isBareRoute(pathname);
  const isFirstLogin = status === "authenticated" && (session as { firstLogin?: boolean } | null)?.firstLogin === true;

  useEffect(() => {
    if (isFirstLogin && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [isFirstLogin, pathname, router]);

  // Se for rota livre/bare (ex.: /login ou /onboarding), renderiza direto
  if (isBare) {
    return <>{children}</>;
  }

  // Enquanto a sessão está carregando no client, ou se firstLogin for true numa rota interna
  if (status === "loading" || (isFirstLogin && pathname !== "/onboarding")) {
    return (
      <div
        data-testid="onboarding-bootstrap-loader"
        className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-400"
      >
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <p className="text-sm">Carregando...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
