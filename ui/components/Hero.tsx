"use client";
import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/card";

const STEPS = ["Classify", "Filter by context", "Route cheapest-good", "Grade & learn", "React to price moves"];

export default function Hero() {
  const [copied, setCopied] = useState(false);
  const base = typeof window !== "undefined" ? `${window.location.origin}/v1` : "/v1";

  function copy() {
    navigator.clipboard?.writeText(base);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <section className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
      <Card className="gap-4 py-7">
        <div className="px-6">
          <h1 className="text-2xl font-semibold tracking-tight text-balance">
            Every request, to the cheapest model that still gets it right.
          </h1>
          <p className="mt-2 max-w-[46ch] text-sm text-muted-foreground">
            Arbiter is a drop-in OpenAI-compatible endpoint. It classifies each request, routes it to the best
            model-for-the-money on the BTL runtime, checks the answer, and learns — so you stop paying premium
            prices for simple work.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {STEPS.map((s, i) => (
              <span key={s} className="rounded-full bg-muted px-3 py-1.5 text-xs font-medium text-muted-foreground">
                <span className="text-foreground font-semibold">{i + 1}</span> · {s}
              </span>
            ))}
          </div>
        </div>
      </Card>

      <Card className="gap-3 py-6">
        <div className="px-6">
          <CardTitle>Integrate in one line</CardTitle>
          <pre className="mt-3 overflow-x-auto rounded-2xl border border-border bg-background p-4 font-mono text-[0.72rem] leading-relaxed">
<span className="text-muted-foreground"># point any OpenAI client here</span>{"\n"}
client = OpenAI({"\n"}
{"  "}<span className="text-primary">base_url</span>=<span className="text-secondary">&quot;{base}&quot;</span>,{"\n"}
{"  "}<span className="text-primary">api_key</span>=<span className="text-secondary">&quot;ignored&quot;</span>){"\n"}
<span className="text-muted-foreground"># model field is ignored — Arbiter picks</span>
          </pre>
          <button
            onClick={copy}
            className="mt-3 rounded-xl border border-border bg-card px-4 py-2 text-xs font-medium transition-all hover:border-primary/50 hover:text-primary"
          >
            {copied ? "Copied ✓" : "Copy base URL"}
          </button>
        </div>
      </Card>
    </section>
  );
}
