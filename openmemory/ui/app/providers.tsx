"use client";

import { Provider } from "react-redux";
import { SessionProvider } from "next-auth/react";
import { store } from "../store/store";
import { AuthBridge } from "@/components/AuthBridge";
import "@/lib/api-client";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <Provider store={store}>
        <AuthBridge />
        {children}
      </Provider>
    </SessionProvider>
  );
}
