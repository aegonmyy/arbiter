"use client";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn, money } from "@/lib/utils";

interface Result {
  answer: string;
  task: string;
  classified_by: string;
  model: string;
  mode: string;
  reason: string;
  quality: number;
  quality_reason: string;
  cost: number;
  saved: number | null;
  eligible_models: number;
}

const EXAMPLES: { label: string; prompt: string }[] = [
  { label: "Math", prompt: "Calculate 47 * 128. Reply with only the number." },
  { label: "Code", prompt: "Write a Python function that returns the nth Fibonacci number." },
  { label: "JSON", prompt: "Return valid JSON with keys city and country for Tokyo." },
  { label: "Factual", prompt: "Who wrote the novel Pride and Prejudice?" },
  { label: "Open", prompt: "Write two sentences about the sound of rain." },
];

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{children}</span>
    </div>
  );
}

export default function Playground() {
  const [prompt, setPrompt] = useState(EXAMPLES[0].prompt);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    if (!prompt.trim() || loading) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: "auto", messages: [{ role: "user", content: prompt }], max_tokens: 400 }),
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
        <CardHeader className="pb-0"><CardTitle>Try it — route a prompt</CardTitle></CardHeader>
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
            placeholder="Ask anything…" />
          <button onClick={run} disabled={loading || !prompt.trim()}
            className="min-h-11 w-full rounded-xl bg-primary px-5 font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-50">
            {loading ? "Routing…" : "Route it"}
          </button>
          <p className="text-[11px] text-muted-foreground">The model field is ignored — Arbiter picks. Sends a real request through the runtime.</p>
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
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <Field label="Task"><span className="capitalize">{result.task}</span> <span className="text-muted-foreground">· {result.classified_by}</span></Field>
                <Field label="Mode"><span className={cn(result.mode === "exploit" ? "text-secondary" : "text-primary")}>{result.mode}</span></Field>
                <Field label="Quality">{result.quality?.toFixed(2)}</Field>
                <Field label="Cost">{money(result.cost)}</Field>
                <Field label="Saved">{result.saved != null && result.saved > 0 ? <span className="text-secondary">−{money(result.saved)}</span> : "—"}</Field>
                <Field label="Eligible">{result.eligible_models} models</Field>
              </div>
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
