"use client";

import { useCallback, useSyncExternalStore } from "react";

export const ADMIN_MODE_STORAGE_KEY = "admin_mode";

// localStorage's "storage" event only fires in other tabs, not the one that
// made the change, so we also broadcast this custom event to keep every
// useAdminMode() instance on the current page in sync.
const ADMIN_MODE_EVENT = "admin-mode-change";

function readAdminMode(): boolean {
  return localStorage.getItem(ADMIN_MODE_STORAGE_KEY) === "true";
}

function getServerSnapshot(): boolean {
  return false;
}

function subscribe(callback: () => void): () => void {
  window.addEventListener("storage", callback);
  window.addEventListener(ADMIN_MODE_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(ADMIN_MODE_EVENT, callback);
  };
}

export function useAdminMode(): [boolean, (value: boolean) => void] {
  const isAdmin = useSyncExternalStore(subscribe, readAdminMode, getServerSnapshot);

  const setAdminMode = useCallback((value: boolean) => {
    localStorage.setItem(ADMIN_MODE_STORAGE_KEY, String(value));
    window.dispatchEvent(new Event(ADMIN_MODE_EVENT));
  }, []);

  return [isAdmin, setAdminMode];
}
