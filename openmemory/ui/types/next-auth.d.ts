import "next-auth";

declare module "next-auth" {
  interface Session {
    /** JWT de sessão emitido pela API OpenMemory (ADR-002). */
    apiAccessToken?: string | null;
    /** Sem máquina vinculada — dispara o wizard de onboarding. */
    firstLogin?: boolean;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    apiAccessToken?: string | null;
    firstLogin?: boolean;
  }
}
