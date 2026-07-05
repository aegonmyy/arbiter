"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn, money } from "@/lib/utils";
import { getApiKey } from "@/lib/onboarding";

const ARBITRAGE_MODEL = "deepseek-chat-v3";
const MATH_PROMPT = "Calculate 4821 * 7. Reply with only the number.";

interface Status {
  saved_pct?: number;
  actual_spend?: number;
  cache_entries?: number;
  overrides?: Record<string, number>;
  alerts?: { direction: string; task: string; model: string }[];
}

interface LastRoute { model: string; mode: string; cost: number; task: string }

export default function DemoPage() {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [status, setStatus] = useState<Status>({});
  const [route, setRoute] = useState<LastRoute | null>(null);

  const auth = () => ({ "Content-Type": "application/json", Authorization: `Bearer ${getApiKey()}` });

  const refresh = useCallback(async () => {
    try {
      const [rep, ov, al] = await Promise.all([
        fetch("/v1/report").then((r) => r.json()),
        fetch("/v1/overview").then((r) => r.json()),
        fetch("/v1/alerts").then((r) => r.json()),
      ]);
      setStatus({
        saved_pct: rep.saved_pct, actual_spend: rep.actual_spend,
        cache_entries: ov.cache_entries, overrides: ov.active_price_overrides,
        alerts: (al || []).slice(0, 5),
      });
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function act(label: string, fn: () => Promise<string>) {
    setBusy(label); setMsg(null);
    try { setMsg(await fn()); } catch (e) { setMsg(`Error: ${(e as Error).message}`); }
    finally { setBusy(null); await refresh(); }
  }

  const post = async (path: string, body?: object) => {
    const r = await fetch(path, { method: "POST", headers: auth(), body: body ? JSON.stringify(body) : undefined });
    if (!r.ok) throw new Error(`${r.status} ${(await r.text()).slice(0, 120)}`);
    return r.json();
  };

  const seed = () => act("seed", async () => {
    const d = await post("/v1/demo/seed");
    return `Seeded. math routes to ${d.routes_to}, ${d.task_types} task types, ${d.saved_pct}% saved, cache ${d.cache_mode}.`;
  });
  const reset = () => act("reset", async () => { await post("/v1/reset"); setRoute(null); return "Reset to a clean slate."; });
  const spike = () => act("spike", async () => {
    await post("/v1/simulate-price", { model: ARBITRAGE_MODEL, multiplier: 8 });
    return `Price of ${ARBITRAGE_MODEL} bumped 8x. Route a math request to see the alert, then again to see it re-route.`;
  });
  const clearSpike = () => act("clear", async () => {
    await post("/v1/simulate-price", { model: ARBITRAGE_MODEL, multiplier: 1 });
    return `Cleared the price override on ${ARBITRAGE_MODEL}.`;
  });
  const routeMath = () => act("route", async () => {
    const d = await post("/v1/chat/completions", { model: "auto", messages: [{ role: "user", content: MATH_PROMPT }], max_tokens: 12 });
    const a = d.arbiter ?? {};
    setRoute({ model: a.model, mode: a.mode, cost: a.cost, task: a.task });
    return `Routed a math request to ${a.model} (${a.mode}), cost ${money(a.cost)}.`;
  });

  const Btn = ({ id, onClick, kind = "ghost", children }: {
    id: string; onClick: () => void; kind?: "primary" | "ghost" | "warn"; children: React.ReactNode;
  }) => (
    <button onClick={onClick} disabled={!!busy}
      className={cn("min-h-11 rounded-xl px-4 text-sm font-semibold transition-all disabled:opacity-50",
        kind === "primary" && "bg-primary text-primary-foreground shadow-sm hover:opacity-90",
        kind === "warn" && "border border-primary/40 bg-primary/5 text-primary hover:bg-primary/10",
        kind === "ghost" && "border border-border bg-card hover:border-primary/40")}>
      {busy === id ? "..." : children}
    </button>
  );

  return (
    <div className="mx-auto min-h-screen max-w-3xl space-y-5 px-4 py-10 sm:px-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Demo control</h1>
          <p className="mt-1 text-sm text-muted-foreground">Stage the instance for a live walkthrough. Operator use.</p>
        </div>
        <Link href="/app" className="text-xs font-medium text-muted-foreground hover:text-foreground">Open dashboard</Link>
      </div>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>1. Set the scene</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2 pt-1">
          <Btn id="seed" kind="primary" onClick={seed}>Seed scenario</Btn>
          <Btn id="reset" onClick={reset}>Reset (clean slate)</Btn>
        </CardContent>
      </Card>

      <Card className="gap-3 py-5">
        <CardHeader className="pb-0"><CardTitle>2. Run the price-arbitrage moment</CardTitle></CardHeader>
        <CardContent className="space-y-3 pt-1">
          <p className="text-xs text-muted-foreground">
            Route a math request (routes to <span className="font-mono">{ARBITRAGE_MODEL}</span>). Then bump its price
            and route again: the first post-bump request fires a price alert, the next re-routes to the cheaper model.
          </p>
          <div className="flex flex-wrap gap-2">
            <Btn id="route" kind="primary" onClick={routeMath}>Route a math request</Btn>
            <Btn id="spike" kind="warn" onClick={spike}>Trigger price spike (8x)</Btn>
            <Btn id="clear" onClick={clearSpike}>Clear spike</Btn>
          </div>
          {route && (
            <div className="rounded-xl border border-border bg-background px-4 py-2.5 text-sm">
              Last route: <span className="font-mono font-semibold">{route.model}</span>{" "}
              <span className={cn(route.mode === "exploit" ? "text-secondary" : "text-primary")}>({route.mode})</span>{" "}
              <span className="text-muted-foreground">- {money(route.cost)}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="gap-3 py-5">
        <CardHeader className="flex-row items-center justify-between pb-0">
          <CardTitle>Live state</CardTitle>
          <button onClick={refresh} className="text-xs font-medium text-muted-foreground hover:text-foreground">Refresh</button>
        </CardHeader>
        <CardContent className="space-y-3 pt-1">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Measured savings" value={status.saved_pct != null ? `${status.saved_pct}%` : "-"} accent="text-secondary" />
            <Stat label="Total spend" value={status.actual_spend != null ? money(status.actual_spend) : "-"} accent="text-primary" />
            <Stat label="Cache entries" value={status.cache_entries != null ? String(status.cache_entries) : "-"} />
            <Stat label="Price overrides" value={String(Object.keys(status.overrides ?? {}).length)} />
          </div>
          <div>
            <span className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">Recent price alerts</span>
            {status.alerts && status.alerts.length > 0 ? (
              <div className="mt-1 space-y-1">
                {status.alerts.map((a, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-1.5 text-xs">
                    <span className="rounded bg-primary/12 px-1.5 py-0.5 font-semibold uppercase text-primary">{a.direction} {a.task}</span>
                    <span className="font-mono">{a.model}</span>
                  </div>
                ))}
              </div>
            ) : <p className="mt-1 text-sm text-muted-foreground">None yet - bump a price and route a request.</p>}
          </div>
        </CardContent>
      </Card>

      {msg && <p className="rounded-xl border border-border bg-card px-4 py-2.5 text-sm text-foreground/80">{msg}</p>}
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl border border-border bg-background px-3 py-2.5">
      <p className={cn("text-lg font-bold tabular-nums", accent)}>{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  );
}
