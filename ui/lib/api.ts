"use client";
import useSWR from "swr";

export interface Report {
  calls: number;
  actual_spend: number;
  baseline_spend: number;
  saved: number;
  saved_pct: number;
}

export interface Overview {
  pool_size: number;
  classifier: { rules: number; model: number; "model-fallback": number };
  alerts: number;
  active_price_overrides: Record<string, number>;
}

export interface Decision {
  ts: number;
  task: string;
  classified_by: string;
  model: string;
  mode: "explore" | "exploit";
  quality: number;
  cost: number;
  saved: number | null;
}

export interface Alert {
  task: string;
  model: string;
  old_unit: number;
  new_unit: number;
  direction: "up" | "down";
  ts: number;
}

export interface PolicyRow {
  model: string;
  n: number;
  quality: number | null;
  avg_cost: number | null;
}
export type Policy = Record<string, PolicyRow[]>;

const fetcher = (url: string) => fetch(url).then((r) => r.json());
const opts = { refreshInterval: 1500, keepPreviousData: true };

export interface PricingModel {
  id: string;
  tier: string;
  context: number;
  in_price: number;
  out_price: number;
  baseline: boolean;
}

export const usePricing = () => useSWR<PricingModel[]>("/v1/pricing", fetcher, { revalidateOnFocus: false });

export const useReport = () => useSWR<Report>("/v1/report", fetcher, opts);
export const useOverview = () => useSWR<Overview>("/v1/overview", fetcher, opts);
export const useRecent = () => useSWR<Decision[]>("/v1/recent", fetcher, opts);
export const useAlerts = () => useSWR<Alert[]>("/v1/alerts", fetcher, opts);
export const usePolicy = () => useSWR<Policy>("/v1/policy", fetcher, opts);
