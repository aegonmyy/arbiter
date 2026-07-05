"use client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useAlerts } from "@/lib/api";

export function PriceAlerts() {
  const { data } = useAlerts();
  return (
    <Card className="gap-2 py-5">
      <CardHeader className="pb-0"><CardTitle>Price alerts</CardTitle></CardHeader>
      <CardContent className="space-y-2 pt-1">
        {!data || data.length === 0
          ? <p className="text-sm text-muted-foreground">No price shifts detected.</p>
          : data.slice(0, 5).map((a, i) => (
            <div key={`${a.ts}-${i}`} className="flex items-center gap-2.5 rounded-xl border border-primary/20 bg-primary/6 px-3 py-2">
              <span className="rounded-lg bg-primary/12 px-2 py-0.5 text-[0.62rem] font-semibold uppercase tracking-wide text-primary">{a.direction} {a.task}</span>
              <span className="truncate font-mono text-[0.72rem]" title={a.model}>{a.model}</span>
            </div>
          ))}
      </CardContent>
    </Card>
  );
}

export function HowItWorks() {
  const items = [
    ["Classify", "rules first; a free model when ambiguous."],
    ["Filter", "keep models that fit the prompt, budget and latency."],
    ["Route", "explore, then exploit the cheapest good model; cost measured from the runtime's headers."],
    ["Cache", "a near-duplicate prompt is served for free."],
    ["Failover", "route around a model that errors, mid-request."],
    ["React", "a price move re-opens exploration and re-routes."],
  ];
  return (
    <Card className="gap-2 py-5">
      <CardHeader className="pb-0"><CardTitle>How it works</CardTitle></CardHeader>
      <CardContent className="pt-1">
        <ul className="space-y-2.5">
          {items.map(([k, v]) => (
            <li key={k} className="text-sm text-muted-foreground">
              <span className="font-semibold text-foreground">{k}</span> - {v}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export function Baseline() {
  const rows = [
    ["Premium default", "gpt-4o"],
    ["Quality tolerance", "0.05"],
    ["Surface", "/v1/chat/completions"],
  ];
  return (
    <Card className="gap-2 py-5">
      <CardHeader className="pb-0"><CardTitle>Baseline</CardTitle></CardHeader>
      <CardContent className="pt-1">
        {rows.map(([k, v], i) => (
          <div key={k} className={`flex justify-between py-2 text-sm ${i > 0 ? "border-t border-border" : ""}`}>
            <span className="text-muted-foreground">{k}</span>
            <span className="font-mono font-semibold">{v}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export default function RightRail() {
  return (
    <div className="flex flex-col gap-4">
      <PriceAlerts />
      <HowItWorks />
      <Baseline />
    </div>
  );
}
