"use client";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn, money } from "@/lib/utils";
import { getApiKey } from "@/lib/onboarding";
import { usePricing } from "@/lib/api";

interface Result {
  answer: string;
  task: string;
  difficulty: string;
  classified_by: string;
  model: string;
  mode: string;
  reason: string;
  quality: number;
  quality_reason: string;
  cost: number;
  latency_ms: number;
  eligible_models: number;
  budget_max_cost: number | null;
  budget_met: boolean | null;
  cache: string;
  cache_mode: string | null;
  cache_similarity: number | null;
  failover_from: string[] | null;
  cascaded_from: string | null;
}

// Log-scale budget slider bounds (USD per request).
const MIN_EXP = -6;   // $0.000001
const MAX_EXP = -1.7; // ~$0.02 (above any pool model for a normal prompt)
const tToBudget = (t: number) => Math.pow(10, MIN_EXP + (t / 100) * (MAX_EXP - MIN_EXP));

const EXAMPLES: { label: string; prompt: string }[] = [
  { label: "Math", prompt: "Calculate 47 * 128. Reply with only the number." },
  { label: "Code", prompt: "Write a Python function that returns the nth Fibonacci number." },
  { label: "JSON", prompt: "Return valid JSON with keys city and country for Tokyo." },
  { label: "Factual", prompt: "Who wrote the novel Pride and Prejudice?" },
  { label: "Open", prompt: "Write two sentences about the sound of rain." },
];

function Field({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{children}</span>
      <span className="text-[10px] leading-tight text-muted-foreground/80">{hint}</span>
    </div>
  );
}

function summarize(r: Result): string {
  if (r.cache === "hit") {
    return `This was a near-duplicate of an earlier prompt, so Arbiter served the stored answer `
      + `for free - no model call at all (${r.cache_mode} match).`;
  }
  const how = r.classified_by === "rules" ? "by fast rules" : "by a free model";
  const learned = r.mode === "escalate"
    ? "the cheap model's answer looked weak, so it escalated to a stronger one"
    : r.mode === "exploit"
      ? "used the cheapest model it has learned is good enough"
      : "is still exploring, so it tried a model to learn about it";
  const tail = r.failover_from?.length
    ? ` It first tried ${r.failover_from.join(", ")}, which errored, and failed over.`
    : "";
  return `Arbiter read this as a ${r.difficulty} ${r.task} task (${how}) and ${learned}: ${r.model}. `
    + `The answer scored ${r.quality?.toFixed(2)} out of 1 and cost ${money(r.cost)}.${tail}`;
}

const OUT_TOKENS = 400;

export default function Playground() {
  const [prompt, setPrompt] = useState(EXAMPLES[0].prompt);
  const [budgetT, setBudgetT] = useState(100); // slider position 0..100 (100 = highest)
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: pricing } = usePricing();

  const budget = tToBudget(budgetT);
  const inTokens = Math.max(1, Math.ceil(prompt.length / 4));
  const models = (pricing ?? [])
    .map((m) => ({ ...m, est: (inTokens * m.in_price + OUT_TOKENS * m.out_price) / 1_000_000 }))
    .sort((a, b) => a.est - b.est);
  const fitting = models.filter((m) => m.est <= budget);
  const routableFit = fitting.filter((m) => m.routable).length;
  const shown = fitting.slice(0, 40);

  async function run() {
    if (!prompt.trim() || loading) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const body: Record<string, unknown> = {
        model: "auto", messages: [{ role: "user", content: prompt }], max_tokens: OUT_TOKENS,
        arbiter_max_cost: budget,
      };
      const res = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${getApiKey()}` },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail ?? data));
        return;
      }
      const a = data.arbiter ?? {};
      setResult({ answer: data.choices?.[0]?.message?.content ?? "", ...a });
    } catch {
      setError("Could not reach the router.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>Try it - route a prompt</CardTitle></CardHeader>
        <CardContent className="space-y-3 pt-1">
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((e) => (
              <button key={e.label} onClick={() => setPrompt(e.prompt)}
                className="rounded-full border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary">
                {e.label}
              </button>
            ))}
          </div>
          <label htmlFor="pg" className="sr-only">Prompt</label>
          <textarea id="pg" value={prompt} onChange={(e) => setPrompt(e.target.value)}
            rows={5} spellCheck={false}
            className="w-full resize-y rounded-2xl border border-border bg-background px-4 py-3 font-mono text-sm outline-none focus:border-primary/50"
            placeholder="Ask anything..." />
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">Budget - max cost per request</span>
              <span className="font-mono text-xs font-semibold">{money(budget, 6)}</span>
            </div>
            <input type="range" min={0} max={100} value={budgetT} step={1}
              onChange={(e) => setBudgetT(Number(e.target.value))}
              aria-label="Max cost per request"
              className="w-full accent-[var(--primary)]" />
            <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
              {shown.map((m) => (
                <div key={m.id} className={cn(
                  "flex items-center justify-between rounded-lg border px-2.5 py-1 text-[0.72rem]",
                  m.routable ? "border-secondary/40 bg-secondary/5" : "border-border")}>
                  <span className="flex items-center gap-2 truncate font-mono">
                    <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", m.routable ? "bg-secondary" : "bg-muted-foreground/40")} />
                    {m.id}
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    {m.routable && <span className="rounded bg-secondary/15 px-1.5 py-0.5 text-[0.58rem] font-semibold uppercase tracking-wide text-secondary">routes here</span>}
                    <span className="tabular-nums text-muted-foreground">{money(m.est, 6)}</span>
                  </span>
                </div>
              ))}
              {fitting.length > shown.length && (
                <p className="px-1 pt-1 text-[11px] text-muted-foreground">and {fitting.length - shown.length} more...</p>
              )}
              {!models.length && <div className="h-8 rounded-lg bg-muted shimmer" />}
            </div>
            <p className="text-[11px] text-muted-foreground">
              {models.length
                ? `${fitting.length} of ${models.length} runtime models fit this budget. Arbiter routes among the ${routableFit} it curates.`
                : "Loading prices..."}
            </p>
          </div>
          <button onClick={run} disabled={loading || !prompt.trim()}
            className="min-h-11 w-full rounded-xl bg-primary px-5 font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50">
            {loading ? "Routing..." : "Route it"}
          </button>
          <p className="text-[11px] text-muted-foreground">The model field is ignored - Arbiter picks. Sends a real request through the runtime.</p>
        </CardContent>
      </Card>

      <Card className="gap-3 py-5" aria-live="polite">
        <CardHeader className="pb-0"><CardTitle>Result</CardTitle></CardHeader>
        <CardContent className="pt-1">
          {loading && <div className="h-40 rounded-2xl border border-border bg-muted shimmer" />}
          {!loading && error && (
            <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
              <div className="font-semibold">Request failed</div>
              <div className="mt-1 break-words font-mono text-xs opacity-80">{error}</div>
            </div>
          )}
          {!loading && !error && !result && (
            <p className="py-10 text-center text-sm text-muted-foreground">Pick an example or write a prompt, then route it.</p>
          )}
          {!loading && result && (
            <div className="space-y-4">
              <p className="rounded-2xl border border-border bg-background px-4 py-3 text-sm leading-relaxed text-foreground/80">
                {summarize(result)}
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Field label="Task" hint="kind of request, and how it was detected">
                  <span className="capitalize">{result.task}</span> <span className="text-muted-foreground">- {result.classified_by}</span></Field>
                <Field label="Difficulty" hint="hard prompts route in their own bucket">
                  <span className="capitalize">{result.difficulty}</span></Field>
                <Field label="Mode" hint="explore/exploit, escalate (cascade), or cache">
                  <span className={cn(result.mode === "exploit" ? "text-secondary" : "text-primary")}>{result.mode}</span></Field>
                <Field label="Quality" hint="0-1 score of the answer">{result.quality?.toFixed(2)}</Field>
                <Field label="Cost" hint="real charge, from the runtime's headers">{money(result.cost)}</Field>
                <Field label="Latency" hint="how long the call took">
                  {result.cache === "hit" ? "-" : `${result.latency_ms} ms`}</Field>
                <Field label="Cache" hint="near-duplicate served free">
                  {result.cache === "hit"
                    ? <span className="text-secondary">hit &middot; {result.cache_mode} {result.cache_similarity?.toFixed(2)}</span>
                    : "miss"}</Field>
                <Field label="Eligible" hint="models within context, budget and latency">{result.eligible_models} models</Field>
                {result.budget_max_cost != null && (
                  <Field label="Budget" hint="max cost you set for this request">
                    <span className={cn(result.budget_met === false && "text-destructive")}>
                      {money(result.budget_max_cost)}{result.budget_met === false ? " (none fit)" : ""}
                    </span>
                  </Field>
                )}
              </div>
              {(result.failover_from?.length || result.cascaded_from) && (
                <p className="rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-muted-foreground">
                  {result.cascaded_from && <>Escalated from <span className="font-mono">{result.cascaded_from}</span> after its answer failed the check. </>}
                  {result.failover_from?.length ? <>Failed over from <span className="font-mono">{result.failover_from.join(", ")}</span> after an upstream error.</> : null}
                </p>
              )}
              <div>
                <span className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">Routed to</span>
                <div className="mt-0.5 truncate font-mono text-sm font-semibold">{result.model}</div>
                <div className="text-xs text-muted-foreground">{result.reason}</div>
              </div>
              <div>
                <span className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">Answer</span>
                <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-2xl border border-border bg-background p-4 text-sm">{result.answer || "(empty)"}</pre>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
