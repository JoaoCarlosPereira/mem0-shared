/**
 * Proteção de rotas da UI (feature auth Google, ADR-002).
 *
 * Com Google configurado (ou AUTH_UI_REQUIRED=1) a UI exige sessão.
 * Em modo legado (--skip-google-auth / AUTH_UI_REQUIRED=0 / sem GOOGLE_CLIENT_ID)
 * o middleware não força /login.
 */
import { NextResponse } from "next/server";

import { auth } from "@/auth";
import { decideAuthRedirect } from "@/lib/auth-routes";
import { isAuthUiRequired } from "@/lib/auth-ui-mode";

export default auth((req) => {
  const session = req.auth as (typeof req.auth & { firstLogin?: boolean }) | null;
  const target = decideAuthRedirect(
    req.nextUrl.pathname,
    !!session,
    session?.firstLogin,
    isAuthUiRequired(),
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
