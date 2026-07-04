"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import ThemeToggle from "@/components/ThemeToggle";
import { cn } from "@/lib/utils";

function OverviewIcon({ className }: { className?: string }) {
  return (<svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25A2.25 2.25 0 0113.5 8.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
  </svg>);
}
function PlaygroundIcon({ className }: { className?: string }) {
  return (<svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.59 14.37a6 6 0 01-5.84 7.38v-4.8m5.84-2.58a14.98 14.98 0 006.16-12.12A14.98 14.98 0 009.63 8.42m5.96 5.95a14.926 14.926 0 01-5.841 2.58m-4.51-2.58a6 6 0 00-3.86 3.86 6 6 0 00-1.13 3.47 6 6 0 003.47-1.13 6 6 0 003.86-3.86m-4.34 4.34L9 15" />
  </svg>);
}
function ActivityIcon({ className }: { className?: string }) {
  return (<svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h4.5l1.5-6 3 12 1.5-6h4.5" />
  </svg>);
}
function ModelsIcon({ className }: { className?: string }) {
  return (<svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0l4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0l-5.571 3-5.571-3" />
  </svg>);
}

const TABS = [
  { label: "Overview", href: "/app", Icon: OverviewIcon },
  { label: "Playground", href: "/app/playground", Icon: PlaygroundIcon },
  { label: "Activity", href: "/app/activity", Icon: ActivityIcon },
  { label: "Models", href: "/app/models", Icon: ModelsIcon },
];

const norm = (p: string) => (p !== "/" && p.endsWith("/") ? p.slice(0, -1) : p);

export default function DashLayout({ children }: { children: React.ReactNode }) {
  const pathname = norm(usePathname());

  return (
    <div className="min-h-screen bg-background">
      {/* Top header */}
      <header className="fixed left-0 right-0 top-0 z-50 flex h-16 items-center border-b border-border/60 bg-card backdrop-blur-xl">
        <div className="flex w-full items-center justify-between gap-6 px-4 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary font-bold text-primary-foreground shadow-sm">A</div>
            <span className="text-lg font-semibold tracking-tight text-foreground">Arbiter</span>
            <span className="ml-1 hidden items-center gap-2 rounded-xl border border-border/70 bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground sm:flex">
              <span className="h-2 w-2 rounded-full bg-secondary pulse-dot" /> Live
            </span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <Link href="/" className="hidden text-xs font-medium text-muted-foreground transition-colors hover:text-foreground sm:block">Home</Link>
            <Link href="/docs/" className="hidden text-xs font-medium text-muted-foreground transition-colors hover:text-foreground sm:block">Docs</Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      {/* Desktop secondary tab bar */}
      <nav className="fixed left-0 right-0 top-16 z-40 hidden h-11 items-center gap-0 border-b border-border bg-card/95 px-8 backdrop-blur-xl sm:flex">
        {TABS.map((t) => {
          const active = pathname === t.href;
          return (
            <Link key={t.href} href={t.href}
              className={cn(
                "-mb-px flex h-full items-center border-b-2 px-5 text-sm font-medium transition-colors",
                active ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground",
              )}>
              {t.label}
            </Link>
          );
        })}
      </nav>

      {/* Page content */}
      <main className="min-h-screen pb-20 pt-16 sm:pb-0 sm:pt-[108px]">{children}</main>

      {/* Mobile bottom tab bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 grid h-16 grid-cols-4 border-t border-border bg-card sm:hidden">
        {TABS.map((t) => {
          const active = pathname === t.href;
          return (
            <Link key={t.href} href={t.href}
              className={cn("flex flex-col items-center justify-center gap-1 transition-colors",
                active ? "text-primary" : "text-muted-foreground")}>
              <t.Icon className="h-5 w-5" />
              <span className="text-[10px] font-medium">{t.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
