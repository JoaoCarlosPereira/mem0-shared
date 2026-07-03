"use client";

/**
 * Nome/avatar da pessoa logada + ação de sair (feature auth Google).
 * Renderiza nada sem sessão (ex.: página de login).
 */
import { signOut, useSession } from "next-auth/react";

import { Button } from "@/components/ui/button";

export function UserMenu() {
  const { data: session } = useSession();
  if (!session?.user) return null;

  const name = session.user.name ?? session.user.email ?? "Usuário";
  const avatar = session.user.image;

  return (
    <div className="flex items-center gap-2" data-testid="user-menu">
      {avatar ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={avatar}
          alt={name}
          width={28}
          height={28}
          className="rounded-full border border-zinc-700"
        />
      ) : null}
      <span className="max-w-[160px] truncate text-sm text-zinc-300">{name}</span>
      <Button
        variant="outline"
        size="sm"
        className="border-zinc-700/50 bg-zinc-900 hover:bg-zinc-800"
        onClick={() => signOut({ redirectTo: "/login" })}
      >
        Sair
      </Button>
    </div>
  );
}
