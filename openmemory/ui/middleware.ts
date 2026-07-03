/**
 * Proteção de rotas da UI (feature auth Google, ADR-002).
 *
 * Toda a UI exige sessão Google; exceções: /login, rotas do próprio NextAuth,
 * o proxy da API (o backend valida o Bearer por conta própria) e assets.
 */
import { NextResponse } from "next/server";

import { auth } from "@/auth";
import { decideAuthRedirect } from "@/lib/auth-routes";

export default auth((req) => {
  const session = req.auth as (typeof req.auth & { firstLogin?: boolean }) | null;
  const target = decideAuthRedirect(
    req.nextUrl.pathname,
    !!session,
    session?.firstLogin,
  );
  if (target) {
    return NextResponse.redirect(new URL(target, req.nextUrl));
  }
  return NextResponse.next();
});

export const config = {
  matcher: [
    "/((?!api/auth|api-proxy|_next/static|_next/image|favicon.ico|logo.svg|.*\\.(?:svg|png|ico)$).*)",
  ],
};
