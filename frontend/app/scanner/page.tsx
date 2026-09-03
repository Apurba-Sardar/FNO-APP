"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Card } from "@/components/ui/card";

import { getApiUrl } from "@/lib/api";
const FRAMES = ["1w", "1d", "4h", "1h", "15m", "5m"];

type Candidate = {
  symbol: string;
  scan_timestamp: string;
  status: string;
  last_price: number | null;
  price_change_percent_24h: number | null;
  volume_24h: number | null;
  relative_volume: number | null;
  spread_percent: number | null;
  estimated_slippage_percent: number | null;
  atr_percent: number | null;
  liquidity: string;
  volatility: string;
  trends: Record<string, string>;
  dominant_direction: string;
  timeframe_alignment: string;
  technical_activity: string;
  warnings: string[];
};
type Stats = {
  total_markets: number;
  eligible_markets: number;
  filtered_markets: number;
  warning_markets: number;
  data_errors: number;
  stale_markets: number;
  processing_time_seconds: number;
  average_processing_time_ms: number;
};
type Status = { status: string; scheduled: boolean; last_scan_at: string | null; stats: Stats | null };

const number = (value: number | null, digits = 3) =>
  value == null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: digits });

export default function ScannerPage() {
  const [items, setItems] = useState<Candidate[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [sortKey, setSortKey] = useState<keyof Candidate>("symbol");
  const [descending, setDescending] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [statusResponse, candidatesResponse] = await Promise.all([
        fetch(`${getApiUrl()}/scanner/status`, { cache: "no-store" }),
        fetch(`${getApiUrl()}/scanner/candidates`, { cache: "no-store" }),
      ]);
      setStatus(await statusResponse.json());
      setItems((await candidatesResponse.json()).items ?? []);
    } catch (cause) {
      setError(String(cause));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(refresh, 10_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function control(action: "run" | "start" | "stop") {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${getApiUrl()}/scanner/${action}`, { method: "POST" });
      if (!response.ok) throw new Error(`scanner ${action} failed (${response.status})`);
      await refresh();
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  const visible = useMemo(() => {
    const matches = items.filter((item) => {
      if (!item.symbol.toLowerCase().includes(query.toLowerCase())) return false;
      if (filter === "eligible") return item.status === "eligible";
      if (["bullish", "bearish", "mixed"].includes(filter))
        return item.dominant_direction === filter;
      if (filter === "high_activity") return item.technical_activity === "high_activity";
      if (filter === "high_volume") return (item.relative_volume ?? 0) >= 2;
      if (filter === "good_liquidity") return ["excellent", "good"].includes(item.liquidity);
      if (filter === "warnings") return item.warnings.length > 0;
      return true;
    });
    return matches.sort((left, right) => {
      const a = left[sortKey] ?? "";
      const b = right[sortKey] ?? "";
      const result = typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b));
      return descending ? -result : result;
    });
  }, [items, query, filter, sortKey, descending]);

  function sort(key: keyof Candidate) {
    if (sortKey === key) setDescending((value) => !value);
    else {
      setSortKey(key);
      setDescending(false);
    }
  }

  const stats = status?.stats;
  return (
    <main className="mx-auto max-w-[1600px] p-3 sm:p-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">Phase 4</p>
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">All-market futures scanner</h1>
          <p className="mt-1 text-sm text-slate-400">Candidate discovery only. No rankings or trade controls.</p>
        </div>
        <div className="flex gap-1.5">
          <button disabled={busy} onClick={() => control("run")} className="rounded-md bg-cyan-400 px-3 py-1.5 text-xs font-bold text-slate-950 hover:bg-cyan-300 disabled:opacity-50">{busy ? "Running…" : "Run once"}</button>
          <button disabled={busy} onClick={() => control("start")} className="rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs font-semibold hover:bg-slate-800 disabled:opacity-50">Schedule</button>
          <button disabled={busy} onClick={() => control("stop")} className="rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-400 hover:text-white disabled:opacity-50">Stop</button>
        </div>
      </header>
      {error && <p className="mt-4 rounded-lg bg-red-950 p-3 text-sm text-red-300">{error}</p>}
      <section className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-6">
        {[
          ["Scanner", status?.status ?? "loading"],
          ["Last scan", status?.last_scan_at ? new Date(status.last_scan_at).toLocaleTimeString() : "—"],
          ["Markets", stats?.total_markets ?? 0],
          ["Eligible", stats?.eligible_markets ?? 0],
          ["Filtered", stats?.filtered_markets ?? 0],
          ["Duration", stats ? `${number(stats.processing_time_seconds, 1)}s` : "—"],
        ].map(([label, value]) => <Card key={String(label)} className="px-3 py-2.5"><p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p><p className="mt-0.5 text-base font-bold capitalize">{value}</p></Card>)}
      </section>
      <Card className="mt-3 p-0 sm:p-0">
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 p-2.5">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pair…" className="min-w-44 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs" />
          <select value={filter} onChange={(event) => setFilter(event.target.value)} className="rounded-md border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs">
            <option value="all">All candidates</option><option value="eligible">Eligible only</option><option value="bullish">Bullish</option><option value="bearish">Bearish</option><option value="mixed">Mixed</option><option value="high_activity">High activity</option><option value="high_volume">High volume</option><option value="good_liquidity">Good liquidity</option><option value="warnings">Warnings</option>
          </select>
          <span className="rounded-full bg-slate-800 px-2.5 py-1 text-[11px] font-semibold text-slate-300">{visible.length} shown</span>
        </div>
        <div className="max-h-[calc(100vh-17rem)] overflow-auto">
          <table className="w-full min-w-[1360px] text-left text-[11px]">
            <thead className="sticky top-0 z-10 bg-slate-900 text-slate-500 shadow-sm"><tr>
              {[["Pair","symbol"],["Price","last_price"],["24h %","price_change_percent_24h"],["Volume","volume_24h"],["RVOL","relative_volume"],["Spread %","spread_percent"],["ATR %","atr_percent"],["Liquidity","liquidity"],["Volatility","volatility"]].map(([label,key]) => <th className="whitespace-nowrap px-2.5 py-2" key={key}><button className="hover:text-cyan-300" onClick={() => sort(key as keyof Candidate)}>{label}{sortKey === key ? (descending ? " ↓" : " ↑") : ""}</button></th>)}
              {FRAMES.map((frame) => <th className="px-2.5 py-2 uppercase" key={frame}>{frame}</th>)}
              <th className="px-2.5 py-2">Direction</th><th className="px-2.5 py-2">Activity</th><th className="px-2.5 py-2">Status</th>
            </tr></thead>
            <tbody>{visible.map((item) => <tr key={item.symbol} className="border-t border-slate-800/80 odd:bg-slate-950/20 hover:bg-cyan-950/25">
              <td className="whitespace-nowrap px-2.5 py-1.5 font-bold text-cyan-300"><Link className="hover:text-cyan-200" href={`/scanner/${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link></td>
              <td className="px-2.5 py-1.5">{number(item.last_price, 6)}</td><td className={`px-2.5 py-1.5 font-semibold ${(item.price_change_percent_24h ?? 0) > 0 ? "text-emerald-400" : (item.price_change_percent_24h ?? 0) < 0 ? "text-rose-400" : ""}`}>{number(item.price_change_percent_24h)}</td><td className="px-2.5 py-1.5">{number(item.volume_24h, 0)}</td><td className="px-2.5 py-1.5">{number(item.relative_volume)}</td><td className="px-2.5 py-1.5">{number(item.spread_percent)}</td><td className="px-2.5 py-1.5">{number(item.atr_percent)}</td><td className="px-2.5 py-1.5 capitalize">{item.liquidity}</td><td className="px-2.5 py-1.5 capitalize">{item.volatility}</td>
              {FRAMES.map((frame) => <td className={`px-2.5 py-1.5 capitalize ${item.trends[frame] === "bullish" ? "text-emerald-400" : item.trends[frame] === "bearish" ? "text-rose-400" : "text-slate-400"}`} key={frame}>{item.trends[frame] ?? "—"}</td>)}
              <td className="px-2.5 py-1.5 capitalize">{item.dominant_direction}</td><td className="whitespace-nowrap px-2.5 py-1.5 capitalize">{item.technical_activity.replaceAll("_"," ")}</td><td className="px-2.5 py-1.5"><span className={`rounded-full px-2 py-0.5 font-semibold capitalize ${item.status === "eligible" ? "bg-emerald-500/10 text-emerald-300" : "bg-slate-800 text-slate-400"}`}>{item.status.replaceAll("_"," ")}</span></td>
            </tr>)}</tbody>
          </table>
        </div>
      </Card>
    </main>
  );
}
