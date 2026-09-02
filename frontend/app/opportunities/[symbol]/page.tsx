"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Factor = { factor_name: string; normalized_score: number; weight: number; weighted_contribution: number; status: string; explanation: string; warnings: string[] };
type Detail = { symbol: string; opportunity_score: number; long_score: number; short_score: number; dominant_direction: string; tier: string; eligible: boolean; current_rank: number | null; factors: Factor[]; strongest_factors: string[]; weakest_factors: string[]; warnings: string[]; explanation_summary: string; estimated_structural_rr: number | null; liquidity: string; volatility: string; data_quality: string; calculated_at: string; hard_gate_reasons: string[] };
const number = (value: number | null, digits = 2) => value == null ? "—" : value.toFixed(digits);

export default function OpportunityDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params.symbol);
  const [item, setItem] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch(`${API}/api/v1/opportunities/${encodeURIComponent(symbol)}`, { cache: "no-store" })
      .then((response) => { if (!response.ok) throw new Error(`Opportunity unavailable (${response.status})`); return response.json(); })
      .then(setItem).catch((cause) => setError(String(cause)));
  }, [symbol]);
  if (error) return <main className="p-6 text-red-300">{error}</main>;
  if (!item) return <main className="p-6 text-slate-400">Loading opportunity analysis…</main>;
  return <main className="mx-auto max-w-6xl p-4 sm:p-6">
    <Link href="/opportunities" className="text-sm text-cyan-300">← Opportunities</Link>
    <header className="mt-4 flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs uppercase tracking-[.2em] text-cyan-400">Opportunity detail · Analysis only</p><h1 className="text-3xl font-semibold">{item.symbol}</h1><p className="mt-2 max-w-3xl text-sm text-slate-400">{item.explanation_summary}</p></div><div className="text-right"><p className="text-xs text-slate-500">Opportunity score</p><p className="text-5xl font-bold text-cyan-300">{number(item.opportunity_score, 1)}</p><p className="font-semibold">Tier {item.tier} · {item.dominant_direction.toUpperCase()}</p></div></header>
    <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">{[["Rank",item.current_rank ? `#${item.current_rank}` : "—"],["Bullish",number(item.long_score,1)],["Bearish",number(item.short_score,1)],["Structural R:R",item.estimated_structural_rr == null ? "Unavailable" : `${number(item.estimated_structural_rr)}R`],["Liquidity",item.liquidity],["Volatility",item.volatility]].map(([label,value]) => <Card key={String(label)}><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg font-semibold capitalize">{value}</p></Card>)}</section>
    <Card className="mt-4"><h2 className="font-semibold">Factor breakdown</h2><div className="mt-4 space-y-4">{item.factors.map((factor) => <div key={factor.factor_name}><div className="flex items-center justify-between gap-3 text-sm"><span className="font-medium capitalize">{factor.factor_name.replaceAll("_"," ")}</span><span>{number(factor.weighted_contribution,2)} / {number(factor.weight,0)}</span></div><div className="mt-1 h-2 overflow-hidden rounded-full bg-slate-800"><div className="h-full rounded-full bg-cyan-400" style={{ width: `${factor.normalized_score}%` }} /></div><p className="mt-1 text-xs text-slate-500">{factor.explanation}</p></div>)}</div><div className="mt-5 border-t border-slate-800 pt-4 text-right text-lg font-semibold">Total: {number(item.opportunity_score,1)} / 100</div></Card>
    <section className="mt-4 grid gap-4 md:grid-cols-2"><Card><h2 className="font-semibold text-emerald-300">Why it scored well</h2><ul className="mt-3 space-y-2 text-sm">{item.strongest_factors.map((factor) => <li key={factor}>✓ {factor.replaceAll("_"," ")}</li>)}</ul></Card><Card><h2 className="font-semibold text-amber-300">Why it is not perfect</h2><ul className="mt-3 space-y-2 text-sm">{item.weakest_factors.map((factor) => <li key={factor}>• {factor.replaceAll("_"," ")}</li>)}</ul></Card></section>
    <Card className="mt-4"><h2 className="font-semibold">Warnings & data quality</h2><p className="mt-2 text-sm capitalize">Data quality: {item.data_quality} · Eligible: {item.eligible ? "yes" : "no"}</p><div className="mt-3 flex flex-wrap gap-2">{item.warnings.length ? item.warnings.map((warning) => <span key={warning} className="rounded-full bg-amber-500/10 px-3 py-1 text-xs text-amber-300">{warning.replaceAll("_"," ")}</span>) : <span className="text-sm text-slate-500">No scoring warnings.</span>}</div><p className="mt-3 text-xs text-slate-500">Calculated {new Date(item.calculated_at).toLocaleString()}. No execution control is available on this page.</p></Card>
  </main>;
}
