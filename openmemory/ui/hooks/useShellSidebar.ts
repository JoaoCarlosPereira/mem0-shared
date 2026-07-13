"use client";

import { useCallback, useEffect, useState } from "react";

const DESKTOP_MQ = "(min-width: 1025px)";

function getIsDesktop(): boolean {
  if (typeof window === "undefined") return true;
  return window.matchMedia(DESKTOP_MQ).matches;
}

export function useShellSidebar() {
  const [sidebarOpen, setSidebarOpen] = useState(getIsDesktop);
  const [isMobile, setIsMobile] = useState(() => !getIsDesktop());

  useEffect(() => {
    const mq = window.matchMedia(DESKTOP_MQ);
    const sync = () => {
      const desktop = mq.matches;
      setIsMobile(!desktop);
      setSidebarOpen(desktop);
    };
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  useEffect(() => {
    if (!sidebarOpen || !isMobile) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSidebarOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [sidebarOpen, isMobile]);

  useEffect(() => {
    if (!isMobile || !sidebarOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [sidebarOpen, isMobile]);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen((prev) => !prev);
  }, []);

  const closeSidebar = useCallback(() => {
    setSidebarOpen(false);
  }, []);

  const closeSidebarIfMobile = useCallback(() => {
    if (window.matchMedia(DESKTOP_MQ).matches) return;
    setSidebarOpen(false);
  }, []);

  return {
    sidebarOpen,
    isMobile,
    toggleSidebar,
    closeSidebar,
    closeSidebarIfMobile,
  };
}
