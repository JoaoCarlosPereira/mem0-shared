import type { LucideIcon } from "lucide-react";
import {
  Home,
  Layers,
  LayoutGrid,
  Settings,
  ShieldCheck,
} from "lucide-react";

export interface ShellNavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  match?: (pathname: string) => boolean;
}

export const MAIN_NAV_ITEMS: ShellNavItem[] = [
  {
    label: "Painel",
    href: "/",
    icon: Home,
    match: (pathname) => pathname === "/",
  },
  {
    label: "Memórias",
    href: "/memories",
    icon: Layers,
    match: (pathname) => pathname.startsWith("/memories") || pathname.startsWith("/memory/"),
  },
  {
    label: "Projetos",
    href: "/apps",
    icon: LayoutGrid,
    match: (pathname) => pathname.startsWith("/apps"),
  },
  {
    label: "Configurações",
    href: "/settings",
    icon: Settings,
    match: (pathname) => pathname.startsWith("/settings"),
  },
];

export const ADMIN_NAV_ITEM: ShellNavItem = {
  label: "Admin",
  href: "/admin",
  icon: ShieldCheck,
  match: (pathname) => pathname.startsWith("/admin"),
};

export function isNavItemActive(pathname: string, item: ShellNavItem): boolean {
  if (item.match) return item.match(pathname);
  if (item.href === "/") return pathname === "/";
  return pathname.startsWith(item.href);
}

export function getPageTitle(pathname: string): string {
  if (pathname === "/") return "Painel";
  if (pathname.startsWith("/memories") || pathname.startsWith("/memory/")) return "Memórias";
  if (pathname.startsWith("/apps")) return "Projetos";
  if (pathname.startsWith("/settings")) return "Configurações";
  return "Mem0-Shared";
}

export function isBareRoute(pathname: string): boolean {
  return pathname.startsWith("/login") || pathname.startsWith("/onboarding");
}

export function isAdminRoute(pathname: string): boolean {
  return pathname.startsWith("/admin");
}
