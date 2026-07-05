"use client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn, money } from "@/lib/utils";
import { useRecent, type Decision } from "@/lib/api";

function Row({ d }: { d: Decision }) {
  const exploit = d.mode === "exploit";
  return (
    <div className="grid grid-cols-[auto_auto_1fr_auto_auto] items-center gap-3 rounded-2xl border border-border bg-background px-3 py-2.5 text-sm">
      <span className="rounded-lg bg-muted px-2 py-0.5 text-[0.63rem] font-semibold uppercase tracking-wide text-muted-foreground">{d.task}</span>
      <span className="rounded-lg border border-border px-2 py-0.5 text-[0.63rem] font-semibold uppercase tracking-wide text-muted-foreground">{d.classified_by}</span>
      <span className="truncate font-mono text-[0.8rem]" title={d.model}>{d.model}</span>
      <span className={cn("rounded-lg px-2 py-0.5 text-[0.63rem] font-semibold uppercase tracking-wide",
        exploit ? "bg-secondary/15 text-secondary" : "bg-primary/12 text-primary")}>{d.mode}</span>
      <span className="text-[0.75rem] tabular-nums text-muted-foreground">{money(d.cost)}</span>
    </div>
  );
}

export default function RoutingFeed() {
  const { data } = useRecent();
  return (
    <Card className="gap-3 py-5">
      <CardHeader className="pb-0"><CardTitle>Live routing decisions</CardTitle></CardHeader>
      <CardContent className="pt-1">
        {!data
          ? <div className="space-y-2">{[0, 1, 2, 3].map((i) => <div key={i} className="h-11 rounded-2xl border border-border bg-muted shimmer" />)}</div>
          : data.length === 0
            ? <p className="rounded-2xl border border-border bg-muted/30 p-6 text-center text-sm text-muted-foreground">Waiting for traffic...</p>
            : <div className="flex max-h-[22rem] flex-col gap-2 overflow-y-auto">{data.map((d, i) => <Row key={`${d.ts}-${i}`} d={d} />)}</div>}
      </CardContent>
    </Card>
  );
}
