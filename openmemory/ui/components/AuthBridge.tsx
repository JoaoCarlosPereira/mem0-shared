"use client";

/**
 * Ponte sessão NextAuth → axios/Redux (feature auth Google, ADR-002).
 *
 * Mantém o Bearer da API no interceptor do axios e o perfil da pessoa
 * (`GET /api/v1/auth/me`) no profileSlice. Renderiza nada.
 */
import { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useDispatch } from "react-redux";
import axios from "axios";

import { setApiAccessToken } from "@/lib/api-client";
import { getApiUrl } from "@/lib/api-url";
import type { AppDispatch } from "@/store/store";
import { clearPersonProfile, setPersonProfile } from "@/store/profileSlice";

export function AuthBridge() {
  const { data: session } = useSession();
  const dispatch = useDispatch<AppDispatch>();

  useEffect(() => {
    const token = (session as any)?.apiAccessToken ?? null;
    setApiAccessToken(token);
    if (!token) {
      dispatch(clearPersonProfile());
      return;
    }
    let cancelled = false;
    axios
      .get(`${getApiUrl()}/api/v1/auth/me`)
      .then((resp) => {
        if (cancelled) return;
        dispatch(
          setPersonProfile({
            email: resp.data.user?.email ?? null,
            displayName: resp.data.user?.display_name ?? null,
            avatarUrl: resp.data.user?.avatar_url ?? null,
            machineHostname: resp.data.machine?.hostname ?? null,
            group: resp.data.group ?? null,
          }),
        );
      })
      .catch(() => {
        // Perfil é informativo; falha não bloqueia a UI.
      });
    return () => {
      cancelled = true;
    };
  }, [session, dispatch]);

  return null;
}
