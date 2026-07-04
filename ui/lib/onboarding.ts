"use client";
import { useEffect, useState } from "react";

const KEY = "arbiter:apikey";

export function saveApiKey(k: string) {
  try { localStorage.setItem(KEY, k); } catch {}
}

export function getApiKey(): string {
  try { return localStorage.getItem(KEY) || ""; } catch { return ""; }
}

export function clearApiKey() {
  try { localStorage.removeItem(KEY); } catch {}
}

// A visitor is "onboarded" once they hold an API key. Returns null until
// mounted (unknown), then true/false, so callers avoid a hydration flash.
export function useOnboarded(): boolean | null {
  const [state, setState] = useState<boolean | null>(null);
  useEffect(() => {
    try { setState(!!localStorage.getItem(KEY)); } catch { setState(false); }
  }, []);
  return state;
}
