"use client";
import { pctOf } from "@/lib/utils";
import { useOverview } from "@/lib/api";

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-2xl border border-border bg-card px-4 py-3.5">
      <span className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className="text-lg font-semibold tabular-nums">{value}</span>
    </div>
  );
}

export default function MiniStats() {
  const { data } = useOverview();
  const c = data?.classifier;
  const total = c ? c.rules + c.model + c["model-fallback"] : 0;
  return (
    <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Mini label="Models in pool" value={data ? String(data.pool_size) : "—"} />
      <Mini label="Classified by rules" value={c ? pctOf(c.rules, total) : "—"} />
      <Mini label="Escalated to model" value={c ? pctOf(c.model + c["model-fallback"], total) : "—"} />
      <Mini label="Price shifts caught" value={data ? String(data.alerts) : "—"} />
    </section>
  );
}
