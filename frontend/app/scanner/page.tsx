"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
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
        fetch(`${API}/api/v1/scanner/status`, { cache: "no-store" }),
        fetch(`${API}/api/v1/scanner/candidates`, { cache: "no-store" }),
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
      const response = await fetch(`${API}/api/v1/scanner/${action}`, { method: "POST" });
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
    <main className="mx-auto max-w-[1600px] p-4 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">Phase 4</p>
          <h1 className="text-2xl font-semibold">All-market futures scanner</h1>
          <p className="mt-1 text-sm text-slate-400">Candidate discovery only. No rankings or trade controls.</p>
        </div>
        <div className="flex gap-2">
          <button disabled={busy} onClick={() => control("run")} className="rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">Run once</button>
          <button disabled={busy} onClick={() => control("start")} className="rounded-lg border border-slate-700 px-3 py-2 text-sm disabled:opacity-50">Start schedule</button>
          <button disabled={busy} onClick={() => control("stop")} className="rounded-lg border border-slate-700 px-3 py-2 text-sm disabled:opacity-50">Stop</button>
        </div>
      </header>
      {error && <p className="mt-4 rounded-lg bg-red-950 p-3 text-sm text-red-300">{error}</p>}
      <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
        {[
          ["Scanner", status?.status ?? "loading"],
          ["Last scan", status?.last_scan_at ? new Date(status.last_scan_at).toLocaleTimeString() : "—"],
          ["Markets", stats?.total_markets ?? 0],
          ["Eligible", stats?.eligible_markets ?? 0],
          ["Filtered", stats?.filtered_markets ?? 0],
          ["Duration", stats ? `${number(stats.processing_time_seconds, 1)}s` : "—"],
        ].map(([label, value]) => <Card key={String(label)}><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold capitalize">{value}</p></Card>)}
      </section>
      <Card className="mt-4">
        <div className="flex flex-wrap gap-3">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search pair" className="min-w-52 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" />
          <select value={filter} onChange={(event) => setFilter(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm">
            <option value="all">All candidates</option><option value="eligible">Eligible only</option><option value="bullish">Bullish</option><option value="bearish">Bearish</option><option value="mixed">Mixed</option><option value="high_activity">High activity</option><option value="high_volume">High volume</option><option value="good_liquidity">Good liquidity</option><option value="warnings">Warnings</option>
          </select>
          <span className="self-center text-sm text-slate-400">{visible.length} shown</span>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-[1500px] w-full text-left text-xs">
            <thead className="text-slate-500"><tr>
              {[["Pair","symbol"],["Price","last_price"],["24h %","price_change_percent_24h"],["Volume","volume_24h"],["RVOL","relative_volume"],["Spread %","spread_percent"],["ATR %","atr_percent"],["Liquidity","liquidity"],["Volatility","volatility"]].map(([label,key]) => <th className="px-2 py-2" key={key}><button onClick={() => sort(key as keyof Candidate)}>{label}</button></th>)}
              {FRAMES.map((frame) => <th className="px-2 py-2 uppercase" key={frame}>{frame}</th>)}
              <th className="px-2 py-2">Direction</th><th className="px-2 py-2">Activity</th><th className="px-2 py-2">Status</th>
            </tr></thead>
            <tbody>{visible.map((item) => <tr key={item.symbol} className="border-t border-slate-800 hover:bg-slate-800/50">
              <td className="px-2 py-2 font-medium text-cyan-300"><Link href={`/scanner/${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link></td>
              <td className="px-2 py-2">{number(item.last_price, 6)}</td><td className="px-2 py-2">{number(item.price_change_percent_24h)}</td><td className="px-2 py-2">{number(item.volume_24h, 0)}</td><td className="px-2 py-2">{number(item.relative_volume)}</td><td className="px-2 py-2">{number(item.spread_percent)}</td><td className="px-2 py-2">{number(item.atr_percent)}</td><td className="px-2 py-2 capitalize">{item.liquidity}</td><td className="px-2 py-2 capitalize">{item.volatility}</td>
              {FRAMES.map((frame) => <td className="px-2 py-2 capitalize" key={frame}>{item.trends[frame] ?? "—"}</td>)}
              <td className="px-2 py-2 capitalize">{item.dominant_direction}</td><td className="px-2 py-2 capitalize">{item.technical_activity.replaceAll("_"," ")}</td><td className="px-2 py-2 capitalize">{item.status.replaceAll("_"," ")}</td>
            </tr>)}</tbody>
          </table>
        </div>
      </Card>
    </main>
  );
}
