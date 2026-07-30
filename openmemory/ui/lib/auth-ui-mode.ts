/**
 * Modo de autenticação da UI (Google vs legado LAN / --skip-google-auth).
 *
 * - AUTH_UI_REQUIRED=0|false|off → legado (não força /login)
 * - AUTH_UI_REQUIRED=1|true|on → exige sessão
 * - sem flag: exige sessão só se GOOGLE_CLIENT_ID (ou NEXT_PUBLIC_*) estiver setado
 */
function truthy(v: string | undefined): boolean | null {
  if (v == null || v.trim() === "") return null;
  const n = v.trim().toLowerCase();
  if (["0", "false", "off", "no"].includes(n)) return false;
  if (["1", "true", "on", "yes"].includes(n)) return true;
  return null;
}

function resolvedPublic(value: string | undefined, placeholder: string): string {
  const v = (value || "").trim();
  // entrypoint.sh leaves the key name as value until replaced; treat as empty.
  if (!v || v === placeholder) return "";
  return v;
}

export function isAuthUiRequired(): boolean {
  const flag =
    truthy(process.env.AUTH_UI_REQUIRED) ??
    truthy(
      resolvedPublic(
        process.env.NEXT_PUBLIC_AUTH_UI_REQUIRED,
        "NEXT_PUBLIC_AUTH_UI_REQUIRED",
      ) || undefined,
    );
  if (flag !== null) return flag;
  const googleId = (
    process.env.GOOGLE_CLIENT_ID ||
    resolvedPublic(
      process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID,
      "NEXT_PUBLIC_GOOGLE_CLIENT_ID",
    ) ||
    ""
  ).trim();
  return Boolean(googleId);
}

/** Legado: login Google desabilitado / skip-google-auth. */
export function isLegacyAuthUi(): boolean {
  return !isAuthUiRequired();
}
