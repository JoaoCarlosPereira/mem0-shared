/**
 * Decisão de redirecionamento de autenticação (pura, testável).
 *
 * Regras (feature auth Google):
 * - sem sessão, qualquer rota protegida redireciona para /login;
 * - com sessão, /login volta para o destino natural (onboarding ou painel);
 * - primeiro login força o wizard /onboarding até ser concluído.
 */
export function decideAuthRedirect(
  pathname: string,
  isLoggedIn: boolean,
  firstLogin?: boolean,
): string | null {
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
