"use client";
import { useEffect, useRef, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn, bigMoney } from "@/lib/utils";
import { useReport } from "@/lib/api";

function useAnimated(value: number | undefined) {
  const [display, setDisplay] = useState<number | null>(null);
  const cur = useRef(0);
  const raf = useRef<number | null>(null);
  const seen = useRef(false);
  useEffect(() => {
    if (value == null) return;
    if (!seen.current) { seen.current = true; cur.current = value; setDisplay(value); return; }
    if (raf.current) cancelAnimationFrame(raf.current);
    const start = cur.current, t0 = performance.now();
    const step = (now: number) => {
      const t = Math.min((now - t0) / 500, 1);
      const e = 1 - Math.pow(1 - t, 3);
      cur.current = start + (value - start) * e;
      setDisplay(cur.current);
      if (t < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => { if (raf.current) cancelAnimationFrame(raf.current); };
  }, [value]);
  return display;
}

function Stat({ label, value, render, sub, className }: {
  label: string; value: number | undefined; render: (v: number) => string; sub: string; className?: string;
}) {
  const d = useAnimated(value);
  return (
    <Card className="gap-2 py-5">
      <CardHeader className="pb-0"><CardTitle>{label}</CardTitle></CardHeader>
      <CardContent className="space-y-1 pt-0">
        {d == null
          ? <span className="inline-block h-8 w-24 rounded-lg bg-muted shimmer" />
          : <p className={cn("text-3xl font-bold tracking-tight tabular-nums", className)}>{render(d)}</p>}
        <p className="text-[11px] text-muted-foreground">{sub}</p>
      </CardContent>
    </Card>
  );
}

export default function StatsBar() {
  const { data } = useReport();
  const proj = data && data.calls > 0 ? (data.saved / data.calls) * 1e6 : undefined;
  return (
    <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Stat label="Saved vs baseline" value={data?.saved_pct} render={(v) => v.toFixed(1) + "%"}
        sub="cheaper than always-baseline" className="text-secondary" />
      <Stat label="Total saved" value={data?.saved} render={bigMoney}
        sub={proj != null ? `~ ${bigMoney(proj)} per 1M requests` : "measuring..."} />
      <Stat label="Actual spend" value={data?.actual_spend} render={bigMoney}
        sub={data ? `vs ${bigMoney(data.baseline_spend)} on baseline` : "-"} />
      <Stat label="Calls routed" value={data?.calls} render={(v) => Math.round(v).toLocaleString()}
        sub="across all task types" className="text-primary" />
    </section>
  );
}
