"use client";
import { useState } from "react";
import StatsBar from "./StatsBar";
import MiniStats from "./MiniStats";
import SavingsChart from "./SavingsChart";
import RoutingFeed from "./RoutingFeed";
import PolicyTable from "./PolicyTable";
import Playground from "./Playground";
import { PriceAlerts, HowItWorks, Baseline } from "./RightRail";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "playground", label: "Playground" },
  { id: "activity", label: "Activity" },
  { id: "models", label: "Models" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function Dashboard() {
  const [tab, setTab] = useState<TabId>("overview");

  function onKey(e: React.KeyboardEvent) {
    const i = TABS.findIndex((t) => t.id === tab);
    if (e.key === "ArrowRight") setTab(TABS[(i + 1) % TABS.length].id);
    if (e.key === "ArrowLeft") setTab(TABS[(i - 1 + TABS.length) % TABS.length].id);
  }

  return (
    <div className="space-y-5">
      {/* tab bar — scrolls horizontally on small screens */}
      <div role="tablist" aria-label="Dashboard sections" onKeyDown={onKey}
        className="-mx-4 flex gap-1 overflow-x-auto px-4 sm:mx-0 sm:px-0">
        {TABS.map((t) => {
          const active = t.id === tab;
          return (
            <button key={t.id} role="tab" id={`tab-${t.id}`} aria-controls={`panel-${t.id}`}
              aria-selected={active} tabIndex={active ? 0 : -1} onClick={() => setTab(t.id)}
              className={cn(
                "min-h-10 whitespace-nowrap rounded-xl px-4 text-sm font-medium transition-colors",
                active ? "bg-primary text-primary-foreground shadow-sm"
                       : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}>
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "overview" && (
        <div role="tabpanel" id="panel-overview" aria-labelledby="tab-overview" className="space-y-5">
          <StatsBar />
          <MiniStats />
          <div className="grid gap-5 lg:grid-cols-3">
            <div className="lg:col-span-2"><SavingsChart /></div>
            <HowItWorks />
          </div>
        </div>
      )}

      {tab === "playground" && (
        <div role="tabpanel" id="panel-playground" aria-labelledby="tab-playground">
          <Playground />
        </div>
      )}

      {tab === "activity" && (
        <div role="tabpanel" id="panel-activity" aria-labelledby="tab-activity" className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2"><RoutingFeed /></div>
          <PriceAlerts />
        </div>
      )}

      {tab === "models" && (
        <div role="tabpanel" id="panel-models" aria-labelledby="tab-models" className="grid gap-5 lg:grid-cols-3">
          <div className="lg:col-span-2"><PolicyTable /></div>
          <Baseline />
        </div>
      )}
    </div>
  );
}
