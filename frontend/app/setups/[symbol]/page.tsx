"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { SetupChart } from "@/components/setup-chart";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

type Result = { strategy: string; status: string; direction: string; setup_quality_score: number; quality: string; entry_zone: { low: number; high: number } | null; trigger_price: number | null; hypothetical_entry: number | null; hypothetical_stop: number | null; hypothetical_target: number | null; risk_reward: number | null; expires_at: string | null; conditions: Array<{ name: string; met: boolean; explanation: string }>; explanations: string[]; warnings: string[] };
type Analysis = { symbol: string; evaluation_timestamp: string; opportunity_score: number; current_price: number | null; timeframe_trends: Record<string, string>; relative_volume: number | null; atr: number | null; spread_percent: number | null; estimated_slippage_percent: number | null; results: Record<string, Result>; best_setup: Result | null; chart: Array<{ timestamp: string; open: number; high: number; low: number; close: number; ema20: number | null; ema50: number | null; vwap: number | null }>; support_levels: number[]; resistance_levels: number[]; warnings: string[] };
const show = (value: number | null | undefined) => value == null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: 6 });

export default function SetupDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params.symbol);
  const [data, setData] = useState<Analysis | null>(null);
  const [selected, setSelected] = useState("trend_pullback");
  const [error, setError] = useState("");
  useEffect(() => { fetch(`${getApiUrl()}/setups/${encodeURIComponent(symbol)}`).then((response) => { if (!response.ok) throw new Error(`setup request failed (${response.status})`); return response.json(); }).then((value) => { setData(value); if (value.best_setup) setSelected(value.best_setup.strategy); }).catch((cause) => setError(String(cause))); }, [symbol]);
  const result = data?.results[selected];
  const levels = useMemo(() => ({ entryLow: result?.entry_zone?.low, entryHigh: result?.entry_zone?.high, trigger: result?.trigger_price, stop: result?.hypothetical_stop, target: result?.hypothetical_target, support: data?.support_levels ?? [], resistance: data?.resistance_levels ?? [] }), [data, result]);
  return <main className="mx-auto max-w-7xl p-4 sm:p-6">
    <Link className="text-sm text-cyan-300" href="/setups">← Setup monitor</Link>
    <div className="mt-3 flex flex-wrap items-end justify-between gap-3"><div><p className="text-xs font-semibold uppercase tracking-[.2em] text-amber-300">SIMULATED / NON-EXECUTABLE</p><h1 className="text-2xl font-semibold">{symbol}</h1></div><p className="text-sm text-slate-400">Evaluated {data ? new Date(data.evaluation_timestamp).toLocaleString() : "—"}</p></div>
    {error && <p className="mt-4 rounded-lg bg-red-950 p-3 text-red-300">{error}</p>}
    <div className="mt-5 flex gap-2">{data && Object.keys(data.results).map((name) => <button className={`rounded-lg px-4 py-2 text-sm ${selected === name ? "bg-cyan-500 text-slate-950" : "bg-slate-800"}`} key={name} onClick={() => setSelected(name)}>{name.replaceAll("_", " ")}</button>)}</div>
    {data && result ? <div className="mt-4 space-y-4">
      <Card><div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6"><div><p className="text-xs text-slate-500">Opportunity score</p><p>{data.opportunity_score.toFixed(1)}/100</p></div><div><p className="text-xs text-slate-500">Setup quality</p><p>{result.setup_quality_score.toFixed(1)} · {result.quality}</p></div><div><p className="text-xs text-slate-500">Strategy / status</p><p>{result.strategy.replaceAll("_", " ")} · {result.status.replaceAll("_", " ")}</p></div><div><p className="text-xs text-slate-500">Direction / current</p><p>{result.direction.toUpperCase()} · {show(data.current_price)}</p></div><div><p className="text-xs text-slate-500">Entry zone / trigger</p><p>{result.entry_zone ? `${show(result.entry_zone.low)}–${show(result.entry_zone.high)}` : "—"} / {show(result.trigger_price)}</p></div><div><p className="text-xs text-slate-500">Stop / target / R:R</p><p>{show(result.hypothetical_stop)} / {show(result.hypothetical_target)} / {show(result.risk_reward)}</p></div></div></Card>
      <Card><h2 className="font-medium">Market context</h2><div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><p>Relative volume: {show(data.relative_volume)}</p><p>ATR: {show(data.atr)}</p><p>Spread: {show(data.spread_percent)}%</p><p>Slippage: {show(data.estimated_slippage_percent)}%</p></div><div className="mt-3 flex flex-wrap gap-2">{Object.entries(data.timeframe_trends).map(([frame, trend]) => <span className="rounded bg-slate-900 px-2 py-1 text-xs uppercase" key={frame}>{frame} {trend}</span>)}</div><p className="mt-3 text-xs text-slate-500">Invalidation: {show(result.hypothetical_stop)} · Expires: {result.expires_at ? new Date(result.expires_at).toLocaleString() : "—"}</p></Card>
      <Card className="overflow-hidden"><h2 className="mb-3 font-medium">Completed 5m candles and analytical levels</h2><SetupChart points={data.chart} levels={levels} /></Card>
      <div className="grid gap-4 lg:grid-cols-2"><Card><h2 className="font-medium">Conditions</h2><div className="mt-3 space-y-3">{result.conditions.map((condition) => <div key={condition.name}><p className={condition.met ? "text-emerald-300" : "text-amber-300"}>{condition.met ? "✓" : "○"} {condition.name.replaceAll("_", " ")}</p><p className="text-xs text-slate-500">{condition.explanation}</p></div>)}</div></Card><Card><h2 className="font-medium">Safety notes</h2><p className="mt-3 text-sm text-slate-300">All prices shown are hypothetical analysis outputs. This page cannot submit an order.</p>{[...result.explanations, ...result.warnings, ...data.warnings].map((note, index) => <p className="mt-2 text-xs text-slate-500" key={`${note}-${index}`}>• {note}</p>)}</Card></div>
    </div> : <Card className="mt-4">Loading deterministic setup analysis…</Card>}
  </main>;
}
