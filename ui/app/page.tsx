"use client";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { useReport, useOverview } from "@/lib/api";

function Nav() {
  return (
    <header className="fixed left-0 right-0 top-0 z-50 border-b border-border/60 bg-card backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-6 px-4 sm:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary font-bold text-primary-foreground shadow-sm">A</div>
          <span className="text-lg font-semibold tracking-tight">Arbiter</span>
        </div>
        <div className="flex items-center gap-3">
          <Link href="/docs/" className="hidden text-sm font-medium text-muted-foreground transition-colors hover:text-foreground sm:block">Docs</Link>
          <ThemeToggle />
          <Link href="/app" className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-90">Launch app</Link>
        </div>
      </div>
    </header>
  );
}

function Hero() {
  const { data: report } = useReport();
  const { data: overview } = useOverview();
  const stats = [
    { label: "Saved vs baseline", value: report ? `${report.saved_pct.toFixed(0)}%` : null, accent: "text-secondary" },
    { label: "Calls routed", value: report ? report.calls.toLocaleString() : null, accent: "text-foreground" },
    { label: "Models in pool", value: overview ? String(overview.pool_size) : null, accent: "text-foreground" },
    { label: "Task types", value: "5", accent: "text-primary" },
  ];
  return (
    <section className="mx-auto max-w-3xl space-y-8 px-6 pb-24 pt-40 text-center">
      <div className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground shadow-sm">
        <span className="h-2 w-2 rounded-full bg-secondary pulse-dot" /> Runs on the BTL runtime
      </div>
      <div className="space-y-4">
        <h1 className="text-5xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
          The cheapest model that <span className="text-secondary">still gets it right.</span>
        </h1>
        <p className="mx-auto max-w-xl text-lg leading-relaxed text-muted-foreground">
          Arbiter is a drop-in OpenAI-compatible router. It sends each request to the best model-for-the-money on
          the BTL runtime, checks the answer, and learns, so you stop paying premium prices for simple work.
        </p>
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link href="/app" className="rounded-xl bg-primary px-7 py-3 text-sm font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-90">Launch app</Link>
        <Link href="/docs/" className="rounded-xl border border-border bg-card px-7 py-3 text-sm font-semibold transition-all hover:border-primary/30">Read the docs</Link>
      </div>
      <div className="grid w-full grid-cols-2 overflow-hidden rounded-[var(--radius)] border border-border bg-card shadow-sm sm:grid-cols-4">
        {stats.map((s, i) => (
          <div key={s.label} className={cn("border-border px-4 py-4 text-center", i % 2 === 0 && "border-r", i < 2 && "border-b sm:border-b-0", "sm:border-r sm:last:border-r-0")}>
            {s.value ? <p className={cn("text-lg font-bold", s.accent)}>{s.value}</p> : <div className="mx-auto h-6 w-14 rounded-lg bg-muted shimmer" />}
            <p className="mt-0.5 text-[10px] text-muted-foreground/70">{s.label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Steps() {
  const steps = [
    { n: "01", title: "Point your client", body: "Change one base URL and keep your OpenAI code exactly as it is. The model field you send is ignored - choosing the model is Arbiter's whole job." },
    { n: "02", title: "It routes each request", body: "Arbiter classifies the request, drops any model whose context cannot hold it, and picks the cheapest one that is still good enough for that kind of task." },
    { n: "03", title: "It proves the savings", body: "Every answer is graded and priced from the runtime's own cost headers. Savings are measured, not guessed, and climb as the router learns." },
  ];
  return (
    <section className="border-t border-border py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-16 text-center">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-primary">How it works</p>
          <h2 className="text-3xl font-bold tracking-tight">Three steps. Then it runs itself.</h2>
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          {steps.map((s) => (
            <Card key={s.n} className="gap-4">
              <div className="px-6">
                <span className="font-mono text-[10px] tracking-widest text-muted-foreground/50">{s.n}</span>
                <h3 className="mb-2 mt-3 text-base font-semibold">{s.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{s.body}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

function Concepts() {
  const items = [
    { title: "Baseline", body: "The premium default (gpt-4o) every saving is measured against. 'Saved' always means versus running everything on the baseline." },
    { title: "Task type", body: "Each request is bucketed: code, math, structured, factual, or open. Routing is learned separately for each type." },
    { title: "Explore vs exploit", body: "Explore means still learning a model. Exploit means using the one it has learned is best. New task types explore first, then settle." },
    { title: "Quality, 0 to 1", body: "A score of how good the answer was, from objective checks for code and math, or a judge model for open-ended work." },
    { title: "Measured savings", body: "Cost comes from the runtime's real per-call headers, not list prices. The savings you see are measured, not estimated." },
    { title: "Reacts to price", body: "If a model's price moves, Arbiter notices, re-learns it, and re-routes. It is live arbitrage, not a one-time choice." },
  ];
  return (
    <section className="border-t border-border bg-muted/30 py-24">
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-14 text-center">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-primary">The essentials</p>
          <h2 className="text-3xl font-bold tracking-tight">Six words to read it fluently.</h2>
          <p className="mx-auto mt-3 max-w-lg text-sm text-muted-foreground">These are the terms you will see across the dashboard. Learn them once and every screen reads cleanly.</p>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((f) => (
            <Card key={f.title} className="gap-3 py-5">
              <div className="px-6">
                <h3 className="mb-1.5 text-sm font-semibold">{f.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">{f.body}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

function GoodToKnow() {
  const items = [
    { title: "Savings start near zero, then climb", body: "New task types explore every model first. That early phase is tuition; savings rise once it settles on the cheap-and-good model." },
    { title: "Cheapest is not always chosen", body: "The rule is the cheapest model whose quality is within tolerance of the best. On hard tasks it correctly pays more." },
    { title: "The most expensive model can score worst", body: "Some premium reasoning models spend a small token budget thinking and return nothing, so they score zero. More money can mean worse." },
    { title: "One shared, permanent brain", body: "Learning is global and survives restarts, not per-user or per-session. Every request makes it smarter and cheaper for everyone." },
  ];
  return (
    <section className="border-t border-border py-24">
      <div className="mx-auto max-w-4xl px-6">
        <div className="mb-14 text-center">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-primary">Good to know</p>
          <h2 className="text-3xl font-bold tracking-tight">A few things that surprise people.</h2>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {items.map((f) => (
            <div key={f.title} className="rounded-[var(--radius)] border border-border bg-card px-5 py-4 shadow-sm">
              <h3 className="mb-1.5 text-sm font-semibold">{f.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function WhyBtl() {
  return (
    <section className="border-t border-border bg-muted/30 py-24">
      <div className="mx-auto max-w-3xl space-y-4 px-6 text-center">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-primary">Why the runtime</p>
        <h2 className="text-3xl font-bold tracking-tight">None of this works without BTL.</h2>
        <p className="mx-auto max-w-xl text-sm leading-relaxed text-muted-foreground">
          One key reaches many models, and every response reports its real cost. A raw provider key gives you
          neither. That is exactly why the measured savings and the price-reaction can only exist on top of the
          runtime - Arbiter routes model choice, the runtime routes providers and reports the bill.
        </p>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="border-t border-border py-24">
      <div className="mx-auto max-w-xl space-y-6 px-6 text-center">
        <h2 className="text-3xl font-bold tracking-tight">See it route a prompt.</h2>
        <p className="text-sm text-muted-foreground">Open the playground, send a real request, and watch it get classified, routed, scored and priced live.</p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link href="/app/playground" className="rounded-xl bg-primary px-8 py-3 text-sm font-semibold text-primary-foreground shadow-sm transition-all hover:opacity-90">Open the playground</Link>
          <Link href="/docs/" className="rounded-xl border border-border bg-card px-8 py-3 text-sm font-semibold transition-all hover:border-primary/30">Read the docs</Link>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-border bg-card py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">A</div>
          <span className="text-sm font-semibold text-foreground/70">Arbiter</span>
        </div>
        <p className="text-center text-xs text-muted-foreground">Routes model choice on the BTL runtime. Savings measured from real cost headers.</p>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <Link href="/docs/" className="transition-colors hover:text-foreground">Docs</Link>
          <a href="https://github.com/aegonmyy/arbiter" target="_blank" rel="noopener noreferrer" className="transition-colors hover:text-foreground">GitHub</a>
        </div>
      </div>
    </footer>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Nav />
      <Hero />
      <Steps />
      <Concepts />
      <GoodToKnow />
      <WhyBtl />
      <CTA />
      <Footer />
    </div>
  );
}
