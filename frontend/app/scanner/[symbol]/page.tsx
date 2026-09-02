"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const FRAMES = ["1w", "1d", "4h", "1h", "15m", "5m"];
type Candidate = Record<string, any>;
const show = (value: number | null | undefined) => value == null ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 6 });

export default function CandidateDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params.symbol);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch(`${API}/api/v1/scanner/candidates/${encodeURIComponent(symbol)}`, { cache: "no-store" })
      .then((response) => { if (!response.ok) throw new Error(`candidate request failed (${response.status})`); return response.json(); })
      .then(setCandidate).catch((cause) => setError(String(cause)));
  }, [symbol]);
  if (error) return <main className="p-6 text-red-300">{error}</main>;
  if (!candidate) return <main className="p-6">Loading candidate analysis…</main>;
  const frame = candidate.timeframes?.["15m"];
  return <main className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
    <Link href="/scanner" className="text-sm text-cyan-300">← Scanner</Link>
    <Card><p className="text-xs uppercase text-slate-500">Candidate detail</p><h1 className="mt-1 text-2xl font-semibold">{candidate.symbol}</h1><div className="mt-3 flex flex-wrap gap-4 text-sm"><span>Status: <b className="capitalize">{candidate.status}</b></span><span>Direction: <b className="capitalize">{candidate.dominant_direction}</b></span><span>Activity: <b className="capitalize">{candidate.technical_activity?.replaceAll("_"," ")}</b></span><span>Scanned: {new Date(candidate.scan_timestamp).toLocaleString()}</span></div></Card>
    <div className="grid gap-4 md:grid-cols-3">
      <Card><h2 className="font-medium">Market</h2><p className="mt-2">Price: {show(candidate.market.last_price)}</p><p>24h volume: {show(candidate.market.volume_24h)}</p><p>24h change: {show(candidate.market.price_change_percent_24h)}%</p></Card>
      <Card><h2 className="font-medium">Liquidity</h2><p className="mt-2 capitalize">{candidate.liquidity.classification}</p><p>Spread: {show(candidate.liquidity.spread_percent)}%</p><p>Estimated slippage: {show(candidate.liquidity.estimated_slippage_percent)}%</p></Card>
      <Card><h2 className="font-medium">Volume & volatility</h2><p className="mt-2">RVOL: {show(candidate.volume.relative_volume)}</p><p>ATR: {show(candidate.volatility.atr_percent)}%</p><p className="capitalize">Suitability: {candidate.volatility.suitability}</p></Card>
    </div>
    <Card><h2 className="font-medium">Multi-timeframe analysis</h2><div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-6">{FRAMES.map((name) => { const item=candidate.timeframes?.[name]; return <div className="rounded-lg bg-slate-950 p-3" key={name}><p className="text-xs uppercase text-slate-500">{name}</p><p className="mt-1 capitalize">{item?.trend ?? "—"}</p><p className="text-xs text-slate-400">Strength {show(item?.trend_strength)}</p></div>; })}</div></Card>
    <div className="grid gap-4 md:grid-cols-2">
      <Card><h2 className="font-medium">15m structure & momentum</h2><p className="mt-2">HH: {frame?.structure?.higher_high ? "yes" : "no"} · HL: {frame?.structure?.higher_low ? "yes" : "no"} · LH: {frame?.structure?.lower_high ? "yes" : "no"} · LL: {frame?.structure?.lower_low ? "yes" : "no"}</p><p className="mt-2 capitalize">Momentum: {frame?.momentum?.price_momentum ?? "—"}</p><p>Potential support: {frame?.structure?.support_levels?.map((level: any) => show(level.price)).join(", ") || "—"}</p><p>Potential resistance: {frame?.structure?.resistance_levels?.map((level: any) => show(level.price)).join(", ") || "—"}</p></Card>
      <Card><h2 className="font-medium">Data quality & warnings</h2><p className="mt-2 capitalize">{candidate.data_quality_status}</p>{candidate.warnings?.length ? <ul className="mt-2 list-disc pl-5 text-sm text-amber-300">{candidate.warnings.map((warning: string) => <li key={warning}>{warning}</li>)}</ul> : <p className="mt-2 text-sm text-emerald-300">No scanner warnings</p>}</Card>
    </div>
  </main>;
}
