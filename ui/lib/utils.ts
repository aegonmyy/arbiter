import { type ClassValue, clsx } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export const money = (v: number | null | undefined, dp = 5) =>
  v == null ? "—" : "$" + Number(v).toFixed(dp);

export const bigMoney = (v: number | null | undefined) =>
  v == null ? "—" : v >= 1
    ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
    : money(v);

export const pctOf = (n: number, d: number) => (d > 0 ? Math.round((100 * n) / d) + "%" : "—");
