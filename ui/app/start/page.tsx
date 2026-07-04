"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { saveApiKey, useOnboarded } from "@/lib/onboarding";

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-2xl border border-border bg-background px-4 py-3">
      <span className="text-sm font-semibold">{k}</span>
      <span className="text-sm leading-relaxed text-muted-foreground">{children}</span>
    </div>
  );
}

const STEPS = [
  {
    eyebrow: "What it is",
    title: "A router, not a model",
    body: (
      <div className="space-y-3">
        <p className="text-sm leading-relaxed text-muted-foreground">
          Arbiter is a drop-in OpenAI-compatible endpoint. You change one base URL and keep your code. For every
          request it picks the cheapest model that still gets the job right, on the BTL runtime.
        </p>
        <pre className="overflow-x-auto rounded-2xl border border-border bg-background p-4 font-mono text-[0.72rem] leading-relaxed">
client = OpenAI(base_url=<span className="text-secondary">&quot;.../v1&quot;</span>, api_key=<span className="text-secondary">&quot;ignored&quot;</span>)</pre>
        <p className="text-xs text-muted-foreground">The model you pass is ignored - choosing it is Arbiter&apos;s whole job.</p>
      </div>
    ),
  },
  {
    eyebrow: "How it decides",
    title: "Classify, filter, route",
    body: (
      <div className="space-y-2.5">
        <Row k="1. Classify">Sort the request into a task type: code, math, structured, factual, or open.</Row>
        <Row k="2. Filter">Drop any model whose context window cannot hold the prompt.</Row>
        <Row k="3. Route">Pick the cheapest model that is still good enough for that task.</Row>
      </div>
    ),
  },
  {
    eyebrow: "The words you will see",
    title: "Four terms to know",
    body: (
      <div className="space-y-2.5">
        <Row k="Baseline">The premium default (gpt-4o) savings are measured against.</Row>
        <Row k="Explore vs exploit">Explore = still learning a model. Exploit = using the one it learned is best.</Row>
        <Row k="Quality (0 to 1)">How good the answer was, from an objective check or a judge model.</Row>
        <Row k="Measured savings">Cost comes from the runtime&apos;s real headers, not list prices.</Row>
      </div>
    ),
  },
  {
    eyebrow: "Good to know",
    title: "A few things that surprise people",
    body: (
      <div className="space-y-2.5">
        <Row k="Savings start low, then climb">The early explore phase is tuition; it settles into the cheap-and-good model.</Row>
        <Row k="Cheapest is not always chosen">On hard tasks it correctly pays more for a model that is actually good enough.</Row>
        <Row k="One shared brain">Learning is global and permanent, not per-user. Every request makes it smarter for everyone.</Row>
      </div>
    ),
  },
  {
    eyebrow: "You are ready",
    title: "Open the app and route a prompt",
    body: (
      <p className="text-sm leading-relaxed text-muted-foreground">
        That is the whole idea. Head to the Playground, send a real request, and watch it get classified, routed,
        scored and priced live. Everything on the dashboard will read cleanly now.
      </p>
    ),
  },
];

export default function StartPage() {
  const [i, setI] = useState(0);
  const step = STEPS[i];
  const last = i === STEPS.length - 1;
  const onboarded = useOnboarded();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mintedKey, setMintedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function finish() {
    if (busy) return;
    if (!/^\S+@\S+\.\S+$/.test(email)) { setError("Enter a valid email."); return; }
    setBusy(true); setError(null);
    try {
      const res = await fetch("/v1/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok || !data.api_key) { setError("Could not create a key. Try again."); setBusy(false); return; }
      saveApiKey(data.api_key);
      setMintedKey(data.api_key);
      setBusy(false);
    } catch {
      setError("Could not reach the server. Try again.");
      setBusy(false);
    }
  }

  function copyKey() {
    if (mintedKey) navigator.clipboard?.writeText(mintedKey);
    setCopied(true); setTimeout(() => setCopied(false), 1200);
  }

  if (mintedKey) {
    return (
      <div className="flex min-h-screen flex-col bg-background">
        <header className="flex h-16 items-center px-4 sm:px-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary font-bold text-primary-foreground shadow-sm">A</div>
            <span className="text-lg font-semibold tracking-tight">Arbiter</span>
          </div>
        </header>
        <main className="flex flex-1 items-center justify-center px-6 pb-16">
          <div className="w-full max-w-lg space-y-5">
            <div className="rounded-[var(--radius)] border border-border bg-card p-6 shadow-sm sm:p-8">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-primary">You&apos;re in</p>
              <h1 className="mb-2 text-2xl font-bold tracking-tight">Here is your API key</h1>
              <p className="mb-4 text-sm text-muted-foreground">Copy it now and keep it safe. It authenticates your requests and is saved in this browser. You can manage or revoke it any time from the API key tab.</p>
              <div className="flex items-center gap-2 rounded-2xl border border-border bg-background px-4 py-2.5">
                <code className="flex-1 truncate font-mono text-sm">{mintedKey}</code>
                <button onClick={copyKey} className="rounded-lg border border-border px-3 py-1 text-xs font-medium hover:border-primary/50 hover:text-primary">{copied ? "Copied" : "Copy"}</button>
              </div>
            </div>
            <button onClick={() => router.push("/app/playground")}
              className="min-h-11 w-full rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90">
              Launch app
            </button>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <header className="flex h-16 items-center justify-between px-4 sm:px-8">
        <Link href="/" className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary font-bold text-primary-foreground shadow-sm">A</div>
          <span className="text-lg font-semibold tracking-tight">Arbiter</span>
        </Link>
        {onboarded === true && (
          <Link href="/app" className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">Skip to app</Link>
        )}
      </header>

      <main className="flex flex-1 items-center justify-center px-6 pb-16">
        <div className="w-full max-w-lg space-y-6">
          {/* progress dots */}
          <div className="flex items-center justify-center gap-2">
            {STEPS.map((_, n) => (
              <span key={n} className={cn("h-1.5 rounded-full transition-all",
                n === i ? "w-6 bg-primary" : n < i ? "w-1.5 bg-primary/50" : "w-1.5 bg-border")} />
            ))}
          </div>

          <div className="rounded-[var(--radius)] border border-border bg-card p-6 shadow-sm sm:p-8">
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-primary">
              Step {i + 1} of {STEPS.length} &middot; {step.eyebrow}
            </p>
            <h1 className="mb-4 text-2xl font-bold tracking-tight">{step.title}</h1>
            {step.body}
            {last && (
              <div className="mt-5 space-y-2">
                <label htmlFor="email" className="text-sm font-medium">Enter your email to get an API key</label>
                <input id="email" type="email" value={email} inputMode="email" autoComplete="email"
                  onChange={(e) => { setEmail(e.target.value); setError(null); }}
                  onKeyDown={(e) => { if (e.key === "Enter") finish(); }}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-border bg-background px-4 py-2.5 text-sm outline-none focus:border-primary/50" />
                <p className="text-xs text-muted-foreground">Your key authenticates your requests and is saved in this browser.</p>
                {error && <p className="text-xs text-destructive">{error}</p>}
              </div>
            )}
          </div>

          <div className="flex items-center justify-between gap-3">
            <button onClick={() => setI((v) => Math.max(0, v - 1))} disabled={i === 0}
              className="min-h-11 rounded-xl border border-border bg-card px-5 text-sm font-medium transition-colors hover:border-primary/40 disabled:opacity-40">
              Back
            </button>
            {last ? (
              <button onClick={finish} disabled={busy}
                className="min-h-11 flex-1 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50">
                {busy ? "Creating your key..." : "Get my key and launch"}
              </button>
            ) : (
              <button onClick={() => setI((v) => Math.min(STEPS.length - 1, v + 1))}
                className="min-h-11 flex-1 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90">
                Next
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
