"use client";
import { useState } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { InfoBanner } from "@/components/ui/InfoBanner";
import { getApiKey } from "@/lib/onboarding";

function CodeBlock({ label, code }: { label: string; code: string }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[0.62rem] font-semibold uppercase tracking-wider text-muted-foreground">{label}</span>
        <button onClick={copy}
          className="rounded-lg border border-border px-2.5 py-1 text-[0.68rem] font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary">
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto rounded-2xl border border-border bg-background p-4 font-mono text-[0.74rem] leading-relaxed">{code}</pre>
    </div>
  );
}

export default function IntegrationPage() {
  const base = typeof window !== "undefined" ? `${window.location.origin}/v1` : "https://arbiter.ameenme.dev/v1";
  const key = (typeof window !== "undefined" && getApiKey()) || "arb_your_key";

  const python = `from openai import OpenAI

client = OpenAI(base_url="${base}", api_key="${key}")

r = client.chat.completions.create(
    model="auto",                       # ignored - Arbiter picks the model
    messages=[{"role": "user", "content": "Calculate 88 * 12"}],
)
print(r.choices[0].message.content)`;

  const node = `import OpenAI from "openai";

const client = new OpenAI({ baseURL: "${base}", apiKey: "${key}" });

const r = await client.chat.completions.create({
  model: "auto",                        // ignored - Arbiter picks
  messages: [{ role: "user", content: "Calculate 88 * 12" }],
});`;

  const curl = `curl ${base}/chat/completions \\
  -H "Authorization: Bearer ${key}" -H "Content-Type: application/json" \\
  -d '{"model":"auto","messages":[{"role":"user","content":"hi"}]}'`;

  const controls = `# optional, non-standard fields (stripped before the runtime)
extra_body={
    "arbiter_max_cost": 0.0005,    # cap cost per request (USD)
    "arbiter_max_latency": 2.0,    # only models that answer under ~2s
    # "arbiter_no_cache": True,    # skip the near-duplicate cache
}`;

  return (
    <div className="mx-auto max-w-3xl space-y-5 px-4 py-6 sm:px-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Integration</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          A drop-in, OpenAI-compatible endpoint. Change the base URL and key, keep the rest of your code.
        </p>
      </div>

      <InfoBanner storageKey="integration-guide">
        The <strong>model</strong> field you send is ignored on purpose - choosing the cheapest model that still
        gets it right is Arbiter&apos;s whole job. Everything else about your request is passed through unchanged.
      </InfoBanner>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>1. Get your API key</CardTitle></CardHeader>
        <CardContent className="space-y-2 pt-1 text-sm text-muted-foreground">
          <p>
            Every request needs an Arbiter key (separate from any provider key). Yours is on the{" "}
            <Link href="/app/key" className="font-medium text-primary hover:underline">API key</Link> tab -
            copy it, and drop it in below where your OpenAI key used to go.
          </p>
        </CardContent>
      </Card>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>2. Point your client at Arbiter</CardTitle></CardHeader>
        <CardContent className="space-y-4 pt-1">
          <CodeBlock label="Python (OpenAI SDK)" code={python} />
          <CodeBlock label="Node (openai)" code={node} />
          <CodeBlock label="curl" code={curl} />
          <p className="text-xs text-muted-foreground">
            Works the same for anything OpenAI-compatible - LangChain, aider, Continue, n8n, or your own service.
          </p>
        </CardContent>
      </Card>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>3. Shape the routing (optional)</CardTitle></CardHeader>
        <CardContent className="space-y-3 pt-1">
          <p className="text-sm text-muted-foreground">
            Three optional fields cap cost, cap latency, or bypass the cache for a request. The SDK sends them via
            <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">extra_body</code>.
          </p>
          <CodeBlock label="Routing controls" code={controls} />
        </CardContent>
      </Card>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>Next steps</CardTitle></CardHeader>
        <CardContent className="pt-1">
          <div className="flex flex-wrap gap-2">
            <Link href="/app/playground"
              className="flex min-h-10 items-center rounded-xl bg-primary px-4 text-xs font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90">
              Try it in the Playground
            </Link>
            <Link href="/docs/developers"
              className="flex min-h-10 items-center rounded-xl border border-border bg-card px-4 text-xs font-medium transition-all hover:border-primary/50 hover:text-primary">
              Full developer guide
            </Link>
            <Link href="/docs/api-reference"
              className="flex min-h-10 items-center rounded-xl border border-border bg-card px-4 text-xs font-medium transition-all hover:border-primary/50 hover:text-primary">
              API reference
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
