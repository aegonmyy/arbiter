"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { getApiKey, clearApiKey } from "@/lib/onboarding";

interface KeyInfo {
  email: string | null;
  status: string;
  used_6h: number; limit_6h: number | null;
  used_week: number; limit_week: number | null;
}

const authFetch = (url: string, opts: RequestInit = {}) =>
  fetch(url, { ...opts, headers: { ...(opts.headers || {}), Authorization: `Bearer ${getApiKey()}` } });

function Meter({ label, used, limit }: { label: string; used: number; limit: number | null }) {
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
  const near = pct >= 80;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono tabular-nums">{used}{limit != null ? ` / ${limit}` : ""}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-all", near ? "bg-destructive" : "bg-secondary")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function ApiKeyCenter() {
  const router = useRouter();
  const key = typeof window !== "undefined" ? getApiKey() : "";
  const { data, mutate } = useSWR<KeyInfo>("/v1/key", (u: string) => authFetch(u).then((r) => r.json()), { refreshInterval: 5000 });
  const [copied, setCopied] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const [busy, setBusy] = useState(false);

  const masked = key ? key.slice(0, 8) + "..." + key.slice(-4) : "";

  function copy() {
    navigator.clipboard?.writeText(key);
    setCopied(true); setTimeout(() => setCopied(false), 1200);
  }

  async function act(action: "pause" | "resume" | "revoke") {
    if (busy) return;
    if (action === "revoke" && !confirm("Revoke this key? It stops working immediately and cannot be undone.")) return;
    setBusy(true);
    await authFetch(`/v1/key/${action}`, { method: "POST" });
    if (action === "revoke") { clearApiKey(); router.replace("/start"); return; }
    await mutate();
    setBusy(false);
  }

  const status = data?.status ?? "…";
  const paused = status === "paused";

  return (
    <div className="mx-auto grid max-w-3xl gap-5">
      <Card className="gap-3 py-5">
        <CardHeader className="pb-0">
          <div className="flex items-center justify-between">
            <CardTitle>Your API key</CardTitle>
            <span className={cn("rounded-lg px-2 py-0.5 text-[0.63rem] font-semibold uppercase tracking-wide",
              paused ? "bg-destructive/15 text-destructive" : "bg-secondary/15 text-secondary")}>{status}</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-1">
          <div className="flex items-center gap-2 rounded-2xl border border-border bg-background px-4 py-2.5">
            <code className="flex-1 truncate font-mono text-sm">{revealed ? key : masked}</code>
            <button onClick={() => setRevealed((v) => !v)} className="text-xs font-medium text-muted-foreground hover:text-foreground">{revealed ? "Hide" : "Reveal"}</button>
            <button onClick={copy} className="rounded-lg border border-border px-3 py-1 text-xs font-medium hover:border-primary/50 hover:text-primary">{copied ? "Copied" : "Copy"}</button>
          </div>
          <p className="text-[11px] text-muted-foreground">Send it as <code className="font-mono">Authorization: Bearer &lt;key&gt;</code> on every request. {data?.email && <>Registered to {data.email}.</>}</p>
        </CardContent>
      </Card>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>Usage</CardTitle></CardHeader>
        <CardContent className="space-y-4 pt-1">
          <Meter label="Last 6 hours" used={data?.used_6h ?? 0} limit={data?.limit_6h ?? null} />
          <Meter label="This week" used={data?.used_week ?? 0} limit={data?.limit_week ?? null} />
          <p className="text-[11px] text-muted-foreground">Rolling windows. Over a limit, requests return 429 until the window frees up.</p>
        </CardContent>
      </Card>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>Controls</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-3 pt-1">
          <button onClick={() => act(paused ? "resume" : "pause")} disabled={busy}
            className="min-h-10 rounded-xl border border-border bg-card px-5 text-sm font-medium transition-colors hover:border-primary/50 disabled:opacity-50">
            {paused ? "Resume key" : "Pause key"}
          </button>
          <button onClick={() => act("revoke")} disabled={busy}
            className="min-h-10 rounded-xl border border-destructive/40 px-5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/5 disabled:opacity-50">
            Revoke key
          </button>
        </CardContent>
      </Card>
    </div>
  );
}
