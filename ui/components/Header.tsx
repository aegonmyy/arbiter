"use client";
import ThemeToggle from "./ThemeToggle";

export default function Header() {
  return (
    <header className="sticky top-0 z-50 h-16 border-b border-border bg-[var(--nav-bg)] backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[82rem] items-center justify-between gap-6 px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary font-bold text-primary-foreground shadow-sm">A</div>
          <span className="text-lg font-semibold tracking-tight">Arbiter</span>
          <span className="hidden items-center rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground sm:flex">
            Routing on&nbsp;<span className="text-foreground">BTL Runtime</span>
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground">
            <span className="h-2 w-2 rounded-full bg-secondary pulse-dot" /> Live
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
