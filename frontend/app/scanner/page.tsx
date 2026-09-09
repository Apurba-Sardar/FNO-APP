"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";
import { formatIST, formatPercent, money } from "@/lib/format";

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

type Status = {
  status: string;
  scheduled: boolean;
  last_scan_at: string | null;
  stats: Stats | null;
};

export default function ScannerPage() {
  const [items, setItems] = useState<Candidate[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [query, setQuery] = useState("");
  const [filterTab, setFilterTab] = useState<"all" | "bullish" | "bearish" | "volume">("all");
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
      setError("");
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
      const endpoint = action === "run" ? "run" : action === "start" ? "start" : "stop";
      const response = await fetch(`${getApiUrl()}/scanner/${endpoint}`, { method: "POST" });
      if (!response.ok) throw new Error(`Scanner action failed (${response.status})`);
      await refresh();
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  const filtered = useMemo(() => {
    return items.filter((item) => {
      const matchesSearch = item.symbol.toLowerCase().includes(query.toLowerCase());
      if (!matchesSearch) return false;
      if (filterTab === "bullish") return item.dominant_direction === "long";
      if (filterTab === "bearish") return item.dominant_direction === "short";
      if (filterTab === "volume") return (item.relative_volume ?? 0) >= 1.2;
      return true;
    });
  }, [items, query, filterTab]);

  return (
    <main className="mx-auto max-w-[1600px] p-4 sm:p-6 space-y-6">
      {/* Top Header Card */}
      <header className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#121217] via-[#09090c] to-[#070709] p-6 sm:p-7 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.95),inset_0_1px_0_0_rgba(255,255,255,0.08)]">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#00D9F5]/10 px-3 py-1 text-[11px] font-bold text-[#00D9F5] border border-[#00D9F5]/30 font-mono shadow-[0_0_15px_rgba(0,217,245,0.15)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#00D9F5] animate-pulse"></span>
                COINDCX PERPETUAL CONTRACTS
              </span>
              <span className="text-xs text-zinc-400 font-mono">499 Live Pairs</span>
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-black tracking-tight text-white">
              Algorithmic Market Scanner
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-zinc-400 max-w-xl">
              Real-time multi-timeframe trend alignment, momentum impulse scoring, and volume surge detection.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => control("run")}
              disabled={busy}
              className="px-4 py-2.5 text-xs font-black flex items-center gap-2 shadow-lg disabled:opacity-50 rounded-xl bg-white text-black hover:bg-zinc-200 transition"
            >
              {busy ? (
                <>
                  <span className="animate-spin">⏳</span> Scanning 499 Pairs...
                </>
              ) : (
                <>
                  <span>⚡</span> Scan Now
                </>
              )}
            </button>

            {status?.scheduled ? (
              <button
                onClick={() => control("stop")}
                disabled={busy}
                className="rounded-xl border border-[#FF3366]/40 bg-[#FF3366]/10 hover:bg-[#FF3366]/20 px-4 py-2.5 text-xs font-bold text-rose-300 transition"
              >
                Pause Auto-Scan
              </button>
            ) : (
              <button
                onClick={() => control("start")}
                disabled={busy}
                className="rounded-xl border border-[#00F5A0]/40 bg-[#00F5A0]/10 hover:bg-[#00F5A0]/20 px-4 py-2.5 text-xs font-bold text-[#00F5A0] transition"
              >
                Start Auto-Scan (5m)
              </button>
            )}
          </div>
        </div>

        {/* Scan Status & IST Timestamp */}
        {status?.last_scan_at && (
          <div className="mt-4 pt-3 border-t border-white/[0.07] flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-400 font-mono">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0] animate-pulse"></span>
              <span>
                Scanner Status: <b className="text-white capitalize">{status.status}</b> · Monitored:{" "}
                <b className="text-[#00D9F5]">{status.stats?.total_markets ?? 499} pairs</b>
              </span>
            </div>
            <div>
              Last Scan Completed: <b className="text-zinc-200">{formatIST(status.last_scan_at)}</b>
              {status.stats?.processing_time_seconds && (
                <span className="text-zinc-500 font-normal"> ({status.stats.processing_time_seconds.toFixed(1)}s scan time)</span>
              )}
            </div>
          </div>
        )}
      </header>

      {error && (
        <div className="rounded-xl border border-[#FF3366]/40 bg-[#FF3366]/10 p-4 text-xs font-semibold text-rose-300 shadow-[0_0_20px_rgba(255,51,102,0.15)]">
          ⚠️ {error}
        </div>
      )}

      {/* Summary KPI Cards */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4">
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 font-mono">Total Markets</span>
          <b className="mt-1 block text-xl font-black text-white font-mono">
            {status?.stats?.total_markets ?? items.length ?? 499} <span className="text-xs font-normal text-zinc-500">Futures</span>
          </b>
          <span className="text-[11px] text-zinc-500 font-mono">CoinDCX USDT pairs</span>
        </Card>

        <Card className="p-4">
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#00F5A0] font-mono">Eligible for Scalping</span>
          <b className="mt-1 block text-xl font-black text-[#00F5A0] font-mono">
            {status?.stats?.eligible_markets ?? 488}
          </b>
          <span className="text-[11px] text-zinc-500 font-mono">Passed liquidity filters</span>
        </Card>

        <Card className="p-4">
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#00D9F5] font-mono">Bullish Momentum</span>
          <b className="mt-1 block text-xl font-black text-[#00D9F5] font-mono">
            {items.filter(i => i.dominant_direction === "long").length} Markets
          </b>
          <span className="text-[11px] text-zinc-500 font-mono">Aligned uptrends</span>
        </Card>

        <Card className="p-4">
          <span className="text-[11px] font-bold uppercase tracking-[0.14em] text-[#FF3366] font-mono">Bearish Pressure</span>
          <b className="mt-1 block text-xl font-black text-rose-400 font-mono">
            {items.filter(i => i.dominant_direction === "short").length} Markets
          </b>
          <span className="text-[11px] text-zinc-500 font-mono">Aligned downtrends</span>
        </Card>
      </section>

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex flex-wrap rounded-2xl border border-white/[0.07] bg-[#0c0c10]/95 p-1.5 text-xs font-semibold shadow-[0_12px_30px_rgba(0,0,0,0.85)]">
          <button
            onClick={() => setFilterTab("all")}
            className={`rounded-xl px-3.5 py-1.5 transition ${filterTab === "all" ? "bg-white/[0.12] text-white shadow-sm" : "text-zinc-400 hover:text-white"}`}
          >
            All Markets ({items.length})
          </button>
          <button
            onClick={() => setFilterTab("bullish")}
            className={`rounded-xl px-3.5 py-1.5 transition ${filterTab === "bullish" ? "bg-[#00F5A0]/20 text-[#00F5A0] border border-[#00F5A0]/30 shadow-[0_0_10px_rgba(0,245,160,0.15)]" : "text-zinc-400 hover:text-white"}`}
          >
            Bullish Breakouts
          </button>
          <button
            onClick={() => setFilterTab("bearish")}
            className={`rounded-xl px-3.5 py-1.5 transition ${filterTab === "bearish" ? "bg-[#FF3366]/20 text-rose-300 border border-[#FF3366]/30 shadow-[0_0_10px_rgba(255,51,102,0.15)]" : "text-zinc-400 hover:text-white"}`}
          >
            Bearish Shorts
          </button>
          <button
            onClick={() => setFilterTab("volume")}
            className={`rounded-xl px-3.5 py-1.5 transition ${filterTab === "volume" ? "bg-[#00D9F5]/20 text-[#00D9F5] border border-[#00D9F5]/30 shadow-[0_0_10px_rgba(0,217,245,0.15)]" : "text-zinc-400 hover:text-white"}`}
          >
            Volume Surge (RVOL &gt; 1.2x)
          </button>
        </div>

        <input
          type="text"
          placeholder="Search 499 coins (e.g. DOGE, XRP, BTC)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full sm:w-72 rounded-xl border border-white/[0.08] bg-[#08080a] px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-[#00D9F5]/60 font-mono"
        />
      </div>

      {/* Modern Markets Data Table */}
      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[950px] text-left text-xs border-collapse">
            <thead className="bg-[#08080a] text-zinc-400 uppercase tracking-[0.14em] text-[10px] font-bold font-mono border-b border-white/[0.07]">
              <tr>
                <th className="py-3.5 px-4">Market Symbol</th>
                <th className="px-3">Current Price</th>
                <th className="px-3">24h Change</th>
                <th className="px-3">Relative Vol (RVOL)</th>
                <th className="px-3">Direction</th>
                <th className="px-3">15m Trend</th>
                <th className="px-3">1h Trend</th>
                <th className="px-3">4h Trend</th>
                <th className="px-3">Liquidity</th>
                <th className="px-3 text-right">Quick Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {filtered.slice(0, 100).map((row) => {
                const change = row.price_change_percent_24h ?? 0;
                const isPositive = change >= 0;
                const isLong = row.dominant_direction === "long";

                return (
                  <tr key={row.symbol} className="hover:bg-white/[0.02] transition">
                    {/* Symbol */}
                    <td className="py-3 px-4 font-bold text-white font-mono">
                      <Link
                        href={`/setups`}
                        className="hover:text-[#00D9F5] transition"
                      >
                        {row.symbol}
                      </Link>
                    </td>

                    {/* Price */}
                    <td className="px-3 font-mono font-medium text-zinc-200">
                      ${money(row.last_price)}
                    </td>

                    {/* 24h Change */}
                    <td className="px-3 font-semibold">
                      <span className={`inline-flex items-center gap-0.5 ${isPositive ? "text-emerald-400" : "text-rose-400"}`}>
                        {isPositive ? "▲" : "▼"} {formatPercent(change)}
                      </span>
                    </td>

                    {/* RVOL */}
                    <td className="px-3 font-mono">
                      {row.relative_volume ? (
                        <span className={`font-semibold ${row.relative_volume >= 1.5 ? "text-cyan-300" : "text-slate-300"}`}>
                          {row.relative_volume.toFixed(2)}x
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>

                    {/* Direction */}
                    <td className="px-3">
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-extrabold uppercase ${
                          isLong
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                        }`}
                      >
                        {isLong ? "LONG" : "SHORT"}
                      </span>
                    </td>

                    {/* 15m, 1h, 4h Trends */}
                    <td className="px-3">
                      <span className={`text-[10px] uppercase font-bold ${row.trends?.["15m"] === "up" ? "text-emerald-400" : row.trends?.["15m"] === "down" ? "text-rose-400" : "text-slate-500"}`}>
                        {row.trends?.["15m"] ?? "—"}
                      </span>
                    </td>
                    <td className="px-3">
                      <span className={`text-[10px] uppercase font-bold ${row.trends?.["1h"] === "up" ? "text-emerald-400" : row.trends?.["1h"] === "down" ? "text-rose-400" : "text-slate-500"}`}>
                        {row.trends?.["1h"] ?? "—"}
                      </span>
                    </td>
                    <td className="px-3">
                      <span className={`text-[10px] uppercase font-bold ${row.trends?.["4h"] === "up" ? "text-emerald-400" : row.trends?.["4h"] === "down" ? "text-rose-400" : "text-slate-500"}`}>
                        {row.trends?.["4h"] ?? "—"}
                      </span>
                    </td>

                    {/* Liquidity */}
                    <td className="px-3 text-slate-400 capitalize">
                      {row.liquidity || "Deep"}
                    </td>

                    {/* Action */}
                    <td className="px-3 text-right">
                      <Link
                        href={`/live`}
                        className="rounded-md bg-slate-800 hover:bg-slate-700 px-2.5 py-1 text-[11px] font-semibold text-cyan-300 transition"
                      >
                        Trade →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </main>
  );
}
