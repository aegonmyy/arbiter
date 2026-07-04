"use client";
import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useReport } from "@/lib/api";

interface Point { i: number; pct: number }

export default function SavingsChart() {
  const { data } = useReport();
  const [points, setPoints] = useState<Point[]>([]);
  const i = useRef(0);

  useEffect(() => {
    if (!data) return;
    const pct = Math.max(0, Math.min(100, data.saved_pct));
    setPoints((prev) => [...prev, { i: i.current++, pct }].slice(-100));
  }, [data]);

  return (
    <Card className="gap-2 py-5">
      <CardHeader className="pb-0"><CardTitle>Savings over time</CardTitle></CardHeader>
      <CardContent className="pt-2">
        <div className="h-[90px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="savefill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--secondary)" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="var(--secondary)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <YAxis domain={[0, 100]} hide />
              <Tooltip
                cursor={{ stroke: "var(--border)" }}
                contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, fontSize: 12 }}
                labelFormatter={() => ""}
                formatter={(v) => [`${Number(v).toFixed(1)}%`, "saved"]}
              />
              <Area type="monotone" dataKey="pct" stroke="var(--secondary)" strokeWidth={2}
                fill="url(#savefill)" isAnimationActive={false} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
