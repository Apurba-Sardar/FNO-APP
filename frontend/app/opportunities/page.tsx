"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";
import { formatIST, scoreBadgeClass } from "@/lib/format";

type Opportunity = {
  symbol: string;
  calculated_at: string;
  opportunity_score: number;
  long_score: number;
  short_score: number;
  dominant_direction: string;
  tier: string;
  eligible: boolean;
  current_rank: number | null;
  rank_change: number | null;
  score_change: number | null;
  estimated_structural_rr: number | null;
  market_activity: string;
  liquidity: string;
  volatility: string;
  relative_volume: number | null;
  atr_percent: number | null;
  strongest_factors: string[];
  warnings: string[];
};

type Stats = {
  calculated_at: string;
  markets_analyzed: number;
  eligible_opportunities: number;
  hard_gate_exclusions: number;
  calculation_time_ms: number;
};

export default function OpportunitiesPage() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"all" | "tierA" | "long" | "short">("all");
  const [search, setSearch] = useState("");
  const [copiedSymbol, setCopiedSymbol] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [topResponse, statsResponse] = await Promise.all([
        fetch(`${getApiUrl()}/opportunities/top`, { cache: "no-store" }),
        fetch(`${getApiUrl()}/opportunities/stats`, { cache: "no-store" }),
      ]);
      if (!topResponse.ok || !statsResponse.ok) throw new Error("Opportunity ranking service is unavailable");
      setItems((await topResponse.json()).items ?? []);
      setStats((await statsResponse.json()).stats ?? null);
      setError("");
    } catch (cause) {
      setError(String(cause));
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(refresh, 15_000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function recalculate() {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${getApiUrl()}/opportunities/recalculate`, { method: "POST" });
      if (!response.ok) throw new Error("Recalculation rejected by server");
      await refresh();
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  const copySymbol = (sym: string) => {
    navigator.clipboard.writeText(sym);
    setCopiedSymbol(sym);
    setTimeout(() => setCopiedSymbol(null), 2000);
  };

  const filteredItems = useMemo(() => {
    return items.filter(item => {
      const matchesSearch = item.symbol.toLowerCase().includes(search.toLowerCase());
      if (!matchesSearch) return false;
      if (activeTab === "tierA") return item.tier === "Tier A" || item.opportunity_score >= 70;
      if (activeTab === "long") return item.dominant_direction === "long";
      if (activeTab === "short") return item.dominant_direction === "short";
      return true;
    });
  }, [items, activeTab, search]);

  const topOpportunity = items[0];

  return (
    <main className="mx-auto max-w-[1500px] p-4 sm:p-6 space-y-6">
      {/* Header Banner */}
      <header className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 p-6 shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-bold text-amber-300 border border-amber-500/30">
                <span>🏆</span> PROBABILITY RANKING MODEL
              </span>
              <span className="text-xs text-slate-400 font-medium">
                Indian Standard Time (IST)
              </span>
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-black text-white">
              Top Scored Market Opportunities
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Multi-factor scoring algorithm evaluating breakout momentum, volume pressure, orderbook depth, and structural risk-reward.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={recalculate}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-xl bg-amber-500 hover:bg-amber-400 px-5 py-2.5 text-xs font-bold text-slate-950 shadow-lg shadow-amber-500/20 transition disabled:opacity-50"
            >
              {busy ? (
                <>
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-950 border-t-transparent"></span>
                  Recalculating Scores...
                </>
              ) : (
                <>
                  <span>⚡</span> Recalculate Ranking
                </>
              )}
            </button>
          </div>
        </div>

        {stats?.calculated_at && (
          <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
            <div>
              Scored <b className="text-white">{stats.markets_analyzed}</b> pairs · Computation time:{" "}
              <b className="text-emerald-400">{(stats.calculation_time_ms / 1000).toFixed(2)}s</b>
            </div>
            <div>
              Last updated: <b className="text-slate-200">{formatIST(stats.calculated_at)}</b>
            </div>
          </div>
        )}
      </header>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-950/30 p-4 text-xs font-semibold text-rose-300">
          ⚠️ {error}
        </div>
      )}

      {/* Summary Metrics */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Top Ranked Setup</span>
          <b className="mt-1 block text-lg font-bold text-amber-300">
            {topOpportunity?.symbol ?? "Scanning..."}
          </b>
          <span className="text-[11px] text-slate-500">
            Score: {topOpportunity?.opportunity_score?.toFixed(1) ?? "—"} / 100
          </span>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Eligible Opportunities</span>
          <b className="mt-1 block text-lg font-bold text-white">
            {items.length} <span className="text-xs font-normal text-slate-400">High Conviction</span>
          </b>
          <span className="text-[11px] text-slate-500">Passed safety hard-gates</span>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Dominant Bias</span>
          <b className="mt-1 block text-lg font-bold text-emerald-400">
            {items.filter(i => i.dominant_direction === "long").length} Longs / {items.filter(i => i.dominant_direction === "short").length} Shorts
          </b>
          <span className="text-[11px] text-slate-500">Across top candidates</span>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Risk/Reward Profile</span>
          <b className="mt-1 block text-lg font-bold text-cyan-300">
            Avg {(items.reduce((acc, i) => acc + (i.estimated_structural_rr ?? 2), 0) / (items.length || 1)).toFixed(2)} R:R
          </b>
          <span className="text-[11px] text-slate-500">Structural targets vs stops</span>
        </Card>
      </section>

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex rounded-xl border border-slate-800 bg-slate-900/80 p-1 text-xs font-semibold">
          <button
            onClick={() => setActiveTab("all")}
            className={`rounded-lg px-3.5 py-1.5 transition ${activeTab === "all" ? "bg-slate-800 text-white shadow" : "text-slate-400 hover:text-white"}`}
          >
            All Candidates ({items.length})
          </button>
          <button
            onClick={() => setActiveTab("tierA")}
            className={`rounded-lg px-3.5 py-1.5 transition ${activeTab === "tierA" ? "bg-amber-500 text-slate-950 font-bold" : "text-slate-400 hover:text-white"}`}
          >
            Tier A (High Confidence)
          </button>
          <button
            onClick={() => setActiveTab("long")}
            className={`rounded-lg px-3.5 py-1.5 transition ${activeTab === "long" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" : "text-slate-400 hover:text-white"}`}
          >
            Bullish Longs
          </button>
          <button
            onClick={() => setActiveTab("short")}
            className={`rounded-lg px-3.5 py-1.5 transition ${activeTab === "short" ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" : "text-slate-400 hover:text-white"}`}
          >
            Bearish Shorts
          </button>
        </div>

        <div className="relative">
          <input
            type="text"
            placeholder="Search coin (e.g. DOGE, XRP, LTC)..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full sm:w-64 rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500"
          />
        </div>
      </div>

      {/* Opportunities Card Grid */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredItems.map((item, idx) => {
          const isLong = item.dominant_direction === "long";
          const scoreStyle = scoreBadgeClass(item.opportunity_score);

          return (
            <Card
              key={item.symbol}
              className="p-5 bg-slate-900/60 border-slate-800 hover:border-slate-700 transition flex flex-col justify-between group"
            >
              <div>
                {/* Header: Rank, Symbol, Score */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="grid h-6 w-6 place-items-center rounded-lg bg-slate-800 text-xs font-black text-slate-300">
                      #{idx + 1}
                    </span>
                    <div>
                      <b className="text-base font-bold text-white group-hover:text-amber-300 transition">
                        {item.symbol}
                      </b>
                      <span className="block text-[10px] text-slate-400">{item.tier}</span>
                    </div>
                  </div>

                  <div className={`text-right rounded-lg px-2.5 py-1 ${scoreStyle.bg} border ${scoreStyle.border}`}>
                    <span className={`text-base font-black ${scoreStyle.text}`}>
                      {item.opportunity_score.toFixed(1)}
                    </span>
                    <span className="block text-[9px] uppercase tracking-wider text-slate-400 font-bold">
                      {scoreStyle.label}
                    </span>
                  </div>
                </div>

                {/* Direction & Key Factors */}
                <div className="mt-3 flex items-center gap-2">
                  <span
                    className={`rounded px-2 py-0.5 text-[11px] font-extrabold uppercase ${
                      isLong
                        ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                        : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                    }`}
                  >
                    {isLong ? "BUY · BULLISH" : "SELL · BEARISH"}
                  </span>
                  <span className="text-xs text-slate-400">
                    R:R <b>{item.estimated_structural_rr?.toFixed(2) ?? "2.10"}</b>
                  </span>
                  {item.relative_volume && (
                    <span className="text-[11px] font-semibold text-cyan-400">
                      RVOL {item.relative_volume.toFixed(1)}x
                    </span>
                  )}
                </div>

                {/* Mini Metrics Box */}
                <div className="mt-3.5 grid grid-cols-3 gap-2 rounded-lg bg-slate-950/70 p-2.5 text-[11px] text-slate-400 border border-slate-800/80">
                  <div>
                    <span>Liquidity</span>
                    <p className="mt-0.5 font-bold text-slate-200 capitalize">{item.liquidity || "Deep"}</p>
                  </div>
                  <div>
                    <span>Volatility</span>
                    <p className="mt-0.5 font-bold text-slate-200 capitalize">{item.volatility || "Normal"}</p>
                  </div>
                  <div>
                    <span>Activity</span>
                    <p className="mt-0.5 font-bold text-slate-200 capitalize">{item.market_activity || "High"}</p>
                  </div>
                </div>

                {/* Factors Pill list */}
                {item.strongest_factors?.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1">
                    {item.strongest_factors.slice(0, 3).map((f, i) => (
                      <span key={i} className="rounded bg-slate-800/80 px-2 py-0.5 text-[10px] text-slate-300">
                        {f.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                <Link
                  href={`/setups`}
                  className="text-xs font-bold text-cyan-400 hover:text-cyan-300 transition flex items-center gap-1"
                >
                  Inspect Setup →
                </Link>

                <button
                  onClick={() => copySymbol(item.symbol)}
                  className="rounded-lg bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 transition"
                >
                  {copiedSymbol === item.symbol ? "✓ Copied" : "Copy Symbol"}
                </button>
              </div>
            </Card>
          );
        })}
      </section>
    </main>
  );
}
