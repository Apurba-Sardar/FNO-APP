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
    <main className="mx-auto max-w-[1600px] p-4 sm:p-8 space-y-7">
      {/* Header Banner - CRED Velvet Matte Obsidian */}
      <header className="cred-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.9)]">
        {/* Subtle Ambient Radial Glows */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-[#FFB800]/10 blur-3xl"></div>
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-[#00D9F5]/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FFB800]/10 px-3 py-1 text-[11px] font-black tracking-wider uppercase text-[#FFB800] border border-[#FFB800]/30 shadow-[0_0_15px_rgba(255,184,0,0.2)]">
                <span>🏆</span> Probability Ranking Engine
              </span>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                Indian Standard Time (IST) Active
              </span>
              <span className="rounded-full bg-[#00F5A0]/10 border border-[#00F5A0]/25 px-3 py-1 text-[11px] font-bold text-[#00F5A0]">
                ⚡ 15s Continuous Scan Sync
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Top Scored Market Opportunities
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              Multi-factor scoring algorithm evaluating breakout momentum, volume pressure, orderbook depth, and structural risk-reward.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={recalculate}
              disabled={busy}
              className="cred-btn-primary rounded-xl px-5 py-2.5 text-xs font-black flex items-center gap-2"
            >
              {busy ? (
                <>
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent"></span>
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
          <div className="relative z-10 mt-6 pt-4 border-t border-white/[0.07] flex flex-wrap items-center justify-between text-xs text-slate-400 gap-2">
            <div>
              Scored <b className="text-white font-mono">{stats.markets_analyzed}</b> pairs · Computation time:{" "}
              <b className="text-[#00F5A0] font-mono">{(stats.calculation_time_ms / 1000).toFixed(2)}s</b>
            </div>
            <div>
              Last synchronized: <b className="text-slate-200 font-mono">{formatIST(stats.calculated_at)}</b>
            </div>
          </div>
        )}
      </header>

      {error && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs font-semibold text-rose-300 shadow-lg">
          ⚠️ {error}
        </div>
      )}

      {/* Summary Metrics - CRED Obsidian Cards */}
      <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Top Ranked Setup</span>
          <b className="mt-2 block text-xl font-black text-[#FFB800] tracking-tight">
            {topOpportunity?.symbol ?? "Scanning..."}
          </b>
          <span className="mt-1 block text-[11px] text-slate-400 font-mono">
            Score: {topOpportunity?.opportunity_score?.toFixed(1) ?? "—"} / 100
          </span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Eligible Opportunities</span>
          <b className="mt-2 block text-xl font-black text-white tracking-tight">
            {items.length} <span className="text-xs font-normal text-slate-400">High Conviction</span>
          </b>
          <span className="mt-1 block text-[11px] text-[#00F5A0] font-mono">Passed safety hard-gates</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Dominant Market Bias</span>
          <b className="mt-2 block text-xl font-black text-[#00F5A0] tracking-tight font-mono">
            {items.filter(i => i.dominant_direction === "long").length}L / {items.filter(i => i.dominant_direction === "short").length}S
          </b>
          <span className="mt-1 block text-[11px] text-slate-400">Across top candidates</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Risk/Reward Profile</span>
          <b className="mt-2 block text-xl font-black text-[#00D9F5] tracking-tight font-mono">
            Avg {(items.reduce((acc, i) => acc + (i.estimated_structural_rr ?? 2), 0) / (items.length || 1)).toFixed(2)} R:R
          </b>
          <span className="mt-1 block text-[11px] text-slate-400">Structural targets vs stops</span>
        </Card>
      </section>

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div className="flex flex-wrap rounded-2xl border border-white/[0.07] bg-[#0a0a0d] p-1.5 text-xs font-semibold shadow-inner">
          <button
            onClick={() => setActiveTab("all")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              activeTab === "all"
                ? "bg-white/[0.1] text-white shadow-[0_2px_8px_rgba(0,0,0,0.5)] border border-white/[0.1]"
                : "text-slate-400 hover:text-white"
            }`}
          >
            All Candidates ({items.length})
          </button>
          <button
            onClick={() => setActiveTab("tierA")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              activeTab === "tierA"
                ? "bg-[#FFB800] text-black font-black shadow-[0_0_15px_rgba(255,184,0,0.4)]"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Tier A (High Confidence)
          </button>
          <button
            onClick={() => setActiveTab("long")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              activeTab === "long"
                ? "bg-[#00F5A0]/20 text-[#00F5A0] border border-[#00F5A0]/40 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Bullish Longs
          </button>
          <button
            onClick={() => setActiveTab("short")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              activeTab === "short"
                ? "bg-[#FF3366]/20 text-[#FF3366] border border-[#FF3366]/40 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
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
            className="w-full sm:w-72 rounded-xl border border-white/[0.08] bg-[#07070a] px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#FFB800] focus:ring-1 focus:ring-[#FFB800]/30 transition"
          />
        </div>
      </div>

      {/* Opportunities Card Grid */}
      <section className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
        {filteredItems.map((item, idx) => {
          const isLong = item.dominant_direction === "long";
          const scoreStyle = scoreBadgeClass(item.opportunity_score);

          return (
            <Card
              key={item.symbol}
              className="p-6 bg-[#0a0a0d] border border-white/[0.07] hover:border-white/20 transition-all duration-300 rounded-2xl flex flex-col justify-between group shadow-xl hover:shadow-[0_20px_40px_rgba(0,0,0,0.8)]"
            >
              <div>
                {/* Header: Rank, Symbol, Score */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="grid h-7 w-7 place-items-center rounded-xl bg-white/[0.04] border border-white/[0.08] text-xs font-black text-slate-300">
                      #{idx + 1}
                    </span>
                    <div>
                      <b className="text-lg font-black text-white group-hover:text-[#FFB800] transition-colors">
                        {item.symbol}
                      </b>
                      <span className="block text-[10px] uppercase tracking-wider text-slate-500 font-bold">{item.tier}</span>
                    </div>
                  </div>

                  <div className={`text-right rounded-xl px-3 py-1.5 ${scoreStyle.bg} border ${scoreStyle.border} shadow-sm`}>
                    <span className={`text-base font-black ${scoreStyle.text} font-mono`}>
                      {item.opportunity_score.toFixed(1)}
                    </span>
                    <span className="block text-[9px] uppercase tracking-wider text-slate-400 font-bold">
                      {scoreStyle.label}
                    </span>
                  </div>
                </div>

                {/* Direction & Key Factors */}
                <div className="mt-4 flex items-center gap-2">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider ${
                      isLong
                        ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30"
                        : "bg-[#FF3366]/15 text-[#FF3366] border border-[#FF3366]/30"
                    }`}
                  >
                    {isLong ? "BUY · BULLISH" : "SELL · BEARISH"}
                  </span>
                  <span className="text-xs text-slate-400 font-mono">
                    R:R <b className="text-white">{item.estimated_structural_rr?.toFixed(2) ?? "2.10"}</b>
                  </span>
                  {item.relative_volume && (
                    <span className="text-[11px] font-bold text-[#00D9F5] font-mono">
                      RVOL {item.relative_volume.toFixed(1)}x
                    </span>
                  )}
                </div>

                {/* Mini Metrics Box */}
                <div className="mt-4 grid grid-cols-3 gap-2 rounded-xl bg-[#060608] p-3 text-[11px] text-slate-400 border border-white/[0.05]">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">Liquidity</span>
                    <p className="mt-0.5 font-bold text-slate-200 capitalize">{item.liquidity || "Deep"}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">Volatility</span>
                    <p className="mt-0.5 font-bold text-slate-200 capitalize">{item.volatility || "Normal"}</p>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-semibold">Activity</span>
                    <p className="mt-0.5 font-bold text-slate-200 capitalize">{item.market_activity || "High"}</p>
                  </div>
                </div>

                {/* Factors Pill list */}
                {item.strongest_factors?.length > 0 && (
                  <div className="mt-3.5 flex flex-wrap gap-1.5">
                    {item.strongest_factors.slice(0, 3).map((f, i) => (
                      <span key={i} className="rounded-md bg-white/[0.04] border border-white/[0.06] px-2 py-0.5 text-[10px] text-slate-300 font-mono">
                        {f.replace(/_/g, " ")}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between gap-3">
                <Link
                  href={`/setups`}
                  className="text-xs font-bold text-[#00D9F5] hover:text-white transition-colors flex items-center gap-1"
                >
                  Inspect Setup →
                </Link>

                <button
                  onClick={() => copySymbol(item.symbol)}
                  className="cred-btn-secondary px-3 py-1.5 rounded-lg text-xs font-semibold"
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
