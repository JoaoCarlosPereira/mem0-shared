/**
 * task_07 (feature auth Google): regras de proteção de rota (middleware).
 */
import { decideAuthRedirect } from "@/lib/auth-routes";

describe("decideAuthRedirect", () => {
  it("sem sessão, rota protegida redireciona para /login", () => {
    expect(decideAuthRedirect("/", false)).toBe("/login");
    expect(decideAuthRedirect("/memories", false)).toBe("/login");
    expect(decideAuthRedirect("/admin/audit", false)).toBe("/login");
  });

  it("sem sessão, /login não redireciona", () => {
    expect(decideAuthRedirect("/login", false)).toBeNull();
  });

  it("com sessão, /login volta ao painel", () => {
    expect(decideAuthRedirect("/login", true, false)).toBe("/");
  });

  it("sem máquina vinculada em /login vai para /onboarding", () => {
    expect(decideAuthRedirect("/login", true, true)).toBe("/onboarding");
  });

  it("sem máquina vinculada força /onboarding em qualquer rota", () => {
    expect(decideAuthRedirect("/", true, true)).toBe("/onboarding");
    expect(decideAuthRedirect("/memories", true, true)).toBe("/onboarding");
    expect(decideAuthRedirect("/onboarding", true, true)).toBeNull();
  });

  it("sessão normal navega livremente", () => {
    expect(decideAuthRedirect("/", true, false)).toBeNull();
    expect(decideAuthRedirect("/settings", true, false)).toBeNull();
  });
});
