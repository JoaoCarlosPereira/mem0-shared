"use client";

import { useSelector } from "react-redux";

import type { ApiSessionStatus } from "@/store/profileSlice";
import type { RootState } from "@/store/store";

export function useApiSessionStatus(): ApiSessionStatus {
  return useSelector((state: RootState) => state.profile.apiSessionStatus);
}

/** True após GET /auth/me confirmar o Bearer da API. */
export function useApiSessionReady(): boolean {
  return useApiSessionStatus() === "valid";
}
