/**
 * Decisão de redirecionamento de autenticação (pura, testável).
 *
 * Regras (feature auth Google):
 * - modo legado (sem Google / AUTH_UI_REQUIRED=0): não força /login;
 * - sem sessão, qualquer rota protegida redireciona para /login;
 * - com sessão, /login volta para o destino natural (onboarding ou painel);
 * - sem máquina vinculada força o wizard /onboarding até ser concluído.
 */
export function decideAuthRedirect(
  pathname: string,
  isLoggedIn: boolean,
  firstLogin?: boolean,
  authUiRequired: boolean = true,
): string | null {
  if (!authUiRequired) {
    // Legado: /login pode ser visitado, mas não bloqueia o restante da UI.
    if (pathname === "/login" && isLoggedIn) {
      return firstLogin ? "/onboarding" : "/";
    }
    return null;
  }
  const isLoginPage = pathname === "/login";
  if (!isLoggedIn) {
    return isLoginPage ? null : "/login";
  }
  if (isLoginPage) {
    return firstLogin ? "/onboarding" : "/";
  }
  if (firstLogin && pathname !== "/onboarding") {
    return "/onboarding";
  }
  return null;
}
