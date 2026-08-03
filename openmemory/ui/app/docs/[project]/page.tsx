"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Rotas Spec antigas → home Kanban (ADR-008). */
export default function DocsProjectRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/docs");
  }, [router]);
  return (
    <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
      Redirecionando para Kanban…
    </div>
  );
}
