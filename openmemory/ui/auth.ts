/**
 * Configuração NextAuth v5 (feature auth Google, ADR-002).
 *
 * A UI conduz o OAuth com o Google; no callback de sign-in o ID token é
 * trocado no backend (`POST /api/v1/auth/google`) pelo JWT de sessão da API —
 * a fonte da verdade de identidade. O JWT da API fica na sessão NextAuth e é
 * anexado como Bearer pelo axios (`lib/api-client`).
 */
import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";

const API_BASE = process.env.API_INTERNAL_URL || "http://localhost:8765";

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  secret: process.env.NEXTAUTH_SECRET || process.env.AUTH_SECRET,
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    }),
    // Device Flow (ADR-007): o login acontece no backend (google.com/device);
    // este provider só converte o JWT da API em sessão NextAuth, validando-o
    // contra /auth/me — a API continua a fonte da verdade.
    Credentials({
      id: "device",
      name: "Google (device flow)",
      credentials: { apiToken: { type: "text" } },
      async authorize(credentials) {
        const apiToken = (credentials?.apiToken as string) || "";
        if (!apiToken) return null;
        try {
          const resp = await fetch(`${API_BASE}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${apiToken}` },
          });
          if (!resp.ok) return null;
          const me = await resp.json();
          return {
            id: me.user.id,
            name: me.user.display_name,
            email: me.user.email,
            image: me.user.avatar_url,
            apiAccessToken: apiToken,
            // Sem máquina vinculada = ainda precisa do onboarding.
            firstLogin: !me.machine,
          } as any;
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async signIn({ account }) {
      // Sem ID token não há como validar no backend — nega o login.
      if (!account?.id_token) return false;
      try {
        const resp = await fetch(`${API_BASE}/api/v1/auth/google`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: account.id_token }),
        });
        // 403 = domínio não permitido; qualquer não-2xx nega o acesso
        // (NextAuth redireciona para /login?error=AccessDenied).
        if (!resp.ok) return false;
        const data = await resp.json();
        (account as any).apiAccessToken = data.access_token;
        // Onboarding depende de máquina vinculada, não de ``first_login`` (criação
        // da pessoa). Usuário já vinculado no segundo login vai direto ao painel.
        let needsOnboarding = true;
        try {
          const meResp = await fetch(`${API_BASE}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${data.access_token}` },
          });
          if (meResp.ok) {
            const me = await meResp.json();
            needsOnboarding = !me.machine;
          }
        } catch {
          /* mantém needsOnboarding=true (fail-safe para o wizard) */
        }
        (account as any).firstLogin = needsOnboarding;
        return true;
      } catch {
        return false;
      }
    },
    async jwt({ token, account, user, trigger, session }) {
      if (account) {
        token.apiAccessToken = (account as any).apiAccessToken;
        token.firstLogin = (account as any).firstLogin;
      }
      // Provider "device" (Credentials): o token vem no objeto user do authorize.
      if (user && (user as any).apiAccessToken) {
        token.apiAccessToken = (user as any).apiAccessToken;
        token.firstLogin = (user as any).firstLogin === true;
      }
      // O wizard de onboarding limpa firstLogin via useSession().update(...).
      if (trigger === "update" && session && "firstLogin" in session) {
        token.firstLogin = (session as { firstLogin?: boolean }).firstLogin === true;
      }
      // Após vínculo da máquina, /auth/me deixa de expor machine — alinha o JWT.
      if (trigger === "update" && token.apiAccessToken) {
        try {
          const resp = await fetch(`${API_BASE}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${token.apiAccessToken}` },
          });
          if (resp.ok) {
            const me = await resp.json();
            if (me.machine) token.firstLogin = false;
          }
        } catch {
          /* mantém o flag atual */
        }
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).apiAccessToken = token.apiAccessToken ?? null;
      (session as any).firstLogin = token.firstLogin === true;
      return session;
    },
  },
});
