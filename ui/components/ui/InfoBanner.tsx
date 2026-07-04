"use client";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export function InfoBanner({ storageKey, children, className }: {
  storageKey: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [dismissed, setDismissed] = useState(true); // start hidden to avoid flash

  useEffect(() => {
    if (!localStorage.getItem(`banner:${storageKey}`)) setDismissed(false);
  }, [storageKey]);

  if (dismissed) return null;

  function dismiss() {
    localStorage.setItem(`banner:${storageKey}`, "1");
    setDismissed(true);
  }

  return (
    <div className={cn(
      "flex items-start gap-3 rounded-[calc(var(--radius)-4px)] border border-primary/20 bg-primary/5 px-4 py-3",
      className
    )}>
      <svg className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
      </svg>
      <p className="flex-1 text-sm leading-relaxed text-foreground/80">{children}</p>
      <button onClick={dismiss} aria-label="Dismiss"
        className="mt-0.5 flex-shrink-0 text-lg leading-none text-muted-foreground/50 transition-colors hover:text-muted-foreground">
        x
      </button>
    </div>
  );
}
