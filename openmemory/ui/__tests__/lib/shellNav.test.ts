import {
  ADMIN_NAV_ITEM,
  MAIN_NAV_ITEMS,
  getPageTitle,
  isDocsBoardPath,
  isNavItemActive,
} from "@/lib/shell-nav";

describe("shell-nav (ADR-008 Kanban)", () => {
  it("expõe Kanban apontando para /docs (não Documentações)", () => {
    const kanban = MAIN_NAV_ITEMS.find((item) => item.label === "Kanban");
    expect(kanban).toBeDefined();
    expect(kanban!.href).toBe("/docs");
    expect(MAIN_NAV_ITEMS.some((item) => item.label === "Documentações")).toBe(
      false,
    );
  });

  it("marca /docs e subrotas como Kanban ativo", () => {
    const kanban = MAIN_NAV_ITEMS.find((item) => item.label === "Kanban")!;
    expect(isNavItemActive("/docs", kanban)).toBe(true);
    expect(isNavItemActive("/docs/mem0-shared", kanban)).toBe(true);
    expect(isNavItemActive("/store", kanban)).toBe(false);
  });

  it("getPageTitle e isDocsBoardPath cobrem home Kanban full-bleed", () => {
    expect(getPageTitle("/docs")).toBe("Kanban");
    expect(getPageTitle("/docs/proj/ws")).toBe("Kanban");
    expect(getPageTitle("/docs/boards/123")).toBe("Kanban");
    expect(isDocsBoardPath("/docs")).toBe(true);
    expect(isDocsBoardPath("/docs/x")).toBe(true);
    expect(isDocsBoardPath("/docs/boards/123")).toBe(true);
    expect(isDocsBoardPath("/store")).toBe(false);
    expect(ADMIN_NAV_ITEM.href).toBe("/admin");
  });
});
