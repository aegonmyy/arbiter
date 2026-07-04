"use client";
import { useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

export default function IntegrationCard() {
  const [copied, setCopied] = useState(false);
  const base = typeof window !== "undefined" ? `${window.location.origin}/v1` : "/v1";

  function copy() {
    navigator.clipboard?.writeText(base);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <Card className="gap-3 py-5">
      <CardHeader className="pb-0"><CardTitle>Integrate in one line</CardTitle></CardHeader>
      <CardContent className="pt-1">
        <pre className="overflow-x-auto rounded-2xl border border-border bg-background p-4 font-mono text-[0.72rem] leading-relaxed">
<span className="text-muted-foreground"># point any OpenAI client here</span>{"\n"}
client = OpenAI({"\n"}
{"  "}<span className="text-primary">base_url</span>=<span className="text-secondary">&quot;{base}&quot;</span>,{"\n"}
{"  "}<span className="text-primary">api_key</span>=<span className="text-secondary">&quot;ignored&quot;</span>)
        </pre>
        <button onClick={copy}
          className="mt-3 min-h-10 rounded-xl border border-border bg-card px-4 text-xs font-medium transition-all hover:border-primary/50 hover:text-primary">
          {copied ? "Copied ✓" : "Copy base URL"}
        </button>
      </CardContent>
    </Card>
  );
}
