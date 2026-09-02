"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { getApiUrl } from "@/lib/api";

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

const number = (value: number | null, digits = 2) =>
  value == null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: digits });

const scoreColor = (score: number) =>
  score >= 80 ? "text-emerald-300" : score >= 70 ? "text-cyan-300" : score >= 60 ? "text-amber-300" : "text-slate-400";

export default function OpportunitiesPage() {
  const [items, setItems] = useState<Opportunity[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [topResponse, statsResponse] = await Promise.all([
        fetch(`${getApiUrl()}/opportunities/top`, { cache: "no-store" }),
        fetch(`${getApiUrl()}/opportunities/stats`, { cache: "no-store" }),
      ]);
      if (!topResponse.ok || !statsResponse.ok) throw new Error("Opportunity service is unavailable");
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
      if (!response.ok) throw new Error(`Recalculation failed (${response.status})`);
      await refresh();
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-[1500px] p-4 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">Phase 5 · Read only</p>
          <h1 className="text-2xl font-semibold">Market opportunities</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">Deterministic setup-quality ranking for further strategy evaluation. Scores are not probabilities or trade instructions.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/scanner" className="rounded-lg border border-slate-700 px-3 py-2 text-sm">Scanner</Link>
          <button disabled={busy} onClick={recalculate} className="rounded-lg bg-cyan-500 px-3 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50">Recalculate</button>
        </div>
      </header>
      {error && <p className="mt-4 rounded-lg bg-red-950 p-3 text-sm text-red-300">{error}</p>}
      <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        {[
          ["Last calculation", stats ? new Date(stats.calculated_at).toLocaleTimeString() : "—"],
          ["Markets analyzed", stats?.markets_analyzed ?? 0],
          ["Eligible", stats?.eligible_opportunities ?? 0],
          ["Hard-gate exclusions", stats?.hard_gate_exclusions ?? 0],
          ["Calculation", stats ? `${number(stats.calculation_time_ms)} ms` : "—"],
        ].map(([label, value]) => <Card key={String(label)}><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></Card>)}
      </section>
      <Card className="mt-4">
        <div className="mb-4 flex items-center justify-between"><div><h2 className="font-semibold">Top ranked opportunities</h2><p className="text-xs text-slate-500">Tie-breaks: score, liquidity, structural R:R, symbol</p></div><span className="text-sm text-slate-400">{items.length} shown</span></div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1150px] text-left text-sm">
            <thead className="text-xs text-slate-500"><tr>{["Rank","Pair","Score","Tier","Direction","Bullish","Bearish","RVOL","Liquidity","ATR %","Structural R:R","Activity","Change"].map((label) => <th className="px-2 py-2" key={label}>{label}</th>)}</tr></thead>
            <tbody>{items.map((item) => <tr key={item.symbol} className="border-t border-slate-800 hover:bg-slate-800/50">
              <td className="px-2 py-3 font-semibold">#{item.current_rank}</td>
              <td className="px-2 py-3"><Link className="font-medium text-cyan-300" href={`/opportunities/${encodeURIComponent(item.symbol)}`}>{item.symbol}</Link></td>
              <td className={`px-2 py-3 text-lg font-bold ${scoreColor(item.opportunity_score)}`}>{number(item.opportunity_score, 1)}</td>
              <td className="px-2 py-3 font-semibold">{item.tier}</td><td className="px-2 py-3 capitalize">{item.dominant_direction}</td>
              <td className="px-2 py-3">{number(item.long_score, 1)}</td><td className="px-2 py-3">{number(item.short_score, 1)}</td>
              <td className="px-2 py-3">{number(item.relative_volume)}×</td><td className="px-2 py-3 capitalize">{item.liquidity}</td><td className="px-2 py-3">{number(item.atr_percent)}%</td><td className="px-2 py-3">{number(item.estimated_structural_rr)}{item.estimated_structural_rr == null ? "" : "R"}</td><td className="px-2 py-3 capitalize">{item.market_activity.replaceAll("_", " ")}</td><td className="px-2 py-3">{item.score_change == null ? "—" : `${item.score_change >= 0 ? "+" : ""}${number(item.score_change)}`}</td>
            </tr>)}</tbody>
          </table>
        </div>
        {!items.length && <p className="py-12 text-center text-sm text-slate-500">Run the Phase 4 scanner, then recalculate opportunities.</p>}
      </Card>
    </main>
  );
}
