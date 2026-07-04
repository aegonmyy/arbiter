"use client";
import { useEffect, useState } from "react";

const KEY = "arbiter:onboarded";

export function markOnboarded() {
  try { localStorage.setItem(KEY, "1"); } catch {}
}

// Returns null until mounted (unknown), then true/false. Null lets callers
// avoid a flash of the wrong state during static hydration.
export function useOnboarded(): boolean | null {
  const [state, setState] = useState<boolean | null>(null);
  useEffect(() => {
    try { setState(!!localStorage.getItem(KEY)); } catch { setState(false); }
  }, []);
  return state;
}
