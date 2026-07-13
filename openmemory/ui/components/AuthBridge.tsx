"use client";

/**
 * Ponte sessão NextAuth → axios/Redux (feature auth Google, ADR-002).
 *
 * Mantém o Bearer da API no interceptor do axios e o perfil da pessoa
 * (`GET /api/v1/auth/me`) no profileSlice. Renderiza nada.
 */
import { useEffect } from "react";
import { signOut, useSession } from "next-auth/react";
import { useDispatch } from "react-redux";
import axios from "axios";

import { setApiAccessToken } from "@/lib/api-client";
import { getApiUrl } from "@/lib/api-url";
import {
  notifySessionExpired,
  registerSessionExpiryHandler,
  resetSessionExpiryGuard,
} from "@/lib/session-expiry";
import type { AppDispatch } from "@/store/store";
import {
  clearPersonProfile,
  setApiSessionStatus,
  setPersonProfile,
} from "@/store/profileSlice";

const SESSION_EXPIRED_LOGIN = "/login?error=SessionExpired";

function handleSessionExpired() {
  setApiAccessToken(null);
  void signOut({ callbackUrl: SESSION_EXPIRED_LOGIN });
}

export function AuthBridge() {
  const { data: session } = useSession();
  const dispatch = useDispatch<AppDispatch>();

  useEffect(() => registerSessionExpiryHandler(handleSessionExpired), []);

  useEffect(() => {
    const token = (session as { apiAccessToken?: string | null } | null)?.apiAccessToken ?? null;
    setApiAccessToken(token);
    resetSessionExpiryGuard();

    if (!token) {
      dispatch(clearPersonProfile());
      return;
    }

    dispatch(setApiSessionStatus("validating"));
    let cancelled = false;
    axios
      .get(`${getApiUrl()}/api/v1/auth/me`)
      .then((resp) => {
        if (cancelled) return;
        dispatch(setApiSessionStatus("valid"));
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
      .catch((err) => {
        if (cancelled) return;
        dispatch(setApiSessionStatus("invalid"));
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          notifySessionExpired();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [session, dispatch]);

  return null;
}
