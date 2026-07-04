"use client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { cn, money } from "@/lib/utils";
import { usePolicy, type PolicyRow } from "@/lib/api";

function chosenModel(rows: PolicyRow[]): string | null {
  const scored = rows.filter((r) => r.quality != null);
  if (!scored.length) return null;
  const bestQ = Math.max(...scored.map((r) => r.quality!));
  const ok = scored.filter((r) => r.quality! >= bestQ - 0.05);
  return ok.reduce((a, b) => ((a.avg_cost ?? 9) <= (b.avg_cost ?? 9) ? a : b)).model;
}

function TaskTable({ task, rows }: { task: string; rows: PolicyRow[] }) {
  const sorted = [...rows].sort((a, b) => (a.avg_cost ?? 9) - (b.avg_cost ?? 9));
  const chosen = chosenModel(rows);
  return (
    <div>
      <div className="mb-1 mt-3 text-[0.8rem] font-semibold capitalize">{task}</div>
      <table className="w-full text-[0.79rem]">
        <thead>
          <tr className="text-[0.62rem] uppercase tracking-wider text-muted-foreground">
            <th className="py-1.5 pr-2 text-left font-medium">Model</th>
            <th className="py-1.5 px-2 text-left font-medium">Runs</th>
            <th className="py-1.5 px-2 text-left font-medium">Quality</th>
            <th className="py-1.5 pl-2 text-left font-medium">Avg cost</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const isC = r.model === chosen;
            const w = Math.round((r.quality ?? 0) * 100);
            return (
              <tr key={r.model} className={cn("border-t border-border", isC && "bg-secondary/8")}>
                <td className="py-1.5 pr-2 font-mono">{r.model}{isC && " ✓"}</td>
                <td className="py-1.5 px-2 tabular-nums">{r.n}</td>
                <td className="py-1.5 px-2">
                  <div className="flex items-center gap-2">
                    <span className="w-8 tabular-nums">{r.quality == null ? "—" : r.quality.toFixed(2)}</span>
                    <span className="h-1.5 flex-1 overflow-hidden rounded bg-muted"><span className="block h-full bg-secondary" style={{ width: `${w}%` }} /></span>
                  </div>
                </td>
                <td className="py-1.5 pl-2 font-mono">{money(r.avg_cost, 7)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function PolicyTable() {
  const { data } = usePolicy();
  const tasks = data ? Object.entries(data) : [];
  return (
    <Card className="gap-2 py-5">
      <CardHeader className="pb-0"><CardTitle>What the router has learned</CardTitle></CardHeader>
      <CardContent className="pt-0">
        {tasks.length === 0
          ? <p className="py-4 text-sm text-muted-foreground">No data yet.</p>
          : tasks.map(([task, rows]) => <TaskTable key={task} task={task} rows={rows} />)}
      </CardContent>
    </Card>
  );
}
