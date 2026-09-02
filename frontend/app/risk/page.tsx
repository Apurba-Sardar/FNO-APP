"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Account = { account_equity: number | null; available_balance: number | null; consecutive_losses: number; open_positions: unknown[] };
type State = { account: Account; daily_pnl: number; daily_loss_percent: number; total_exposure: number; exposure_percent: number; trading_lock: string; block_reasons: string[] };
type Config = { risk_per_trade_percent: number; max_daily_loss_percent: number; max_consecutive_losses: number; max_open_positions: number; max_total_exposure_percent: number };
type Decision = { symbol: string; strategy: string; direction: string; allowed: boolean; status: string; risk_amount: number; position_quantity: number; position_notional: number; maximum_loss: number; estimated_rr: number; rejection_reasons: string[] };
const show = (value: number | null | undefined, suffix = "") => value == null ? "Unavailable" : `${value.toLocaleString(undefined, { maximumFractionDigits: 4 })}${suffix}`;

export default function RiskCenterPage() {
  const [state, setState] = useState<State | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([fetch(`${API}/api/v1/risk/status`).then((r) => r.json()), fetch(`${API}/api/v1/risk/config`).then((r) => r.json()), fetch(`${API}/api/v1/risk/decisions?limit=500`).then((r) => r.json())]).then(([status, settings, rows]) => { setState(status.state); setConfig(settings); setDecisions(rows.items ?? []); }).catch((cause) => setError(String(cause))); }, []);
  return <main className="mx-auto max-w-7xl p-4 sm:p-6">
    <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">Phase 7 · non-executable</p>
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-2xl font-semibold">Risk Center</h1><p className="text-sm text-slate-400">Central portfolio guard and hypothetical sizing authority.</p></div><span className={`rounded-full px-4 py-2 text-sm font-semibold uppercase ${state?.trading_lock === "open" ? "bg-emerald-950 text-emerald-300" : "bg-red-950 text-red-300"}`}>{state?.trading_lock ?? "loading"}</span></div>
    {error && <p className="mt-4 rounded-lg bg-red-950 p-3 text-red-300">{error}</p>}
    <section className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card><p className="text-xs text-slate-500">Account equity</p><p className="mt-1 text-xl">{show(state?.account.account_equity)}</p></Card>
      <Card><p className="text-xs text-slate-500">Available balance</p><p className="mt-1 text-xl">{show(state?.account.available_balance)}</p></Card>
      <Card><p className="text-xs text-slate-500">Risk per trade</p><p className="mt-1 text-xl">{show(config?.risk_per_trade_percent, "%")}</p></Card>
      <Card><p className="text-xs text-slate-500">Today&apos;s P&amp;L / loss</p><p className="mt-1 text-xl">{show(state?.daily_pnl)} · {show(state?.daily_loss_percent, "%")}</p><p className="text-xs text-slate-500">Limit {show(config?.max_daily_loss_percent, "%")}</p></Card>
      <Card><p className="text-xs text-slate-500">Consecutive losses</p><p className="mt-1 text-xl">{show(state?.account.consecutive_losses)} / {show(config?.max_consecutive_losses)}</p></Card>
      <Card><p className="text-xs text-slate-500">Open positions</p><p className="mt-1 text-xl">{state?.account.open_positions.length ?? 0} / {config?.max_open_positions ?? "—"}</p></Card>
      <Card><p className="text-xs text-slate-500">Total exposure</p><p className="mt-1 text-xl">{show(state?.total_exposure)}</p><p className="text-xs text-slate-500">{show(state?.exposure_percent, "%")} / {show(config?.max_total_exposure_percent, "%")}</p></Card>
      <Card><p className="text-xs text-slate-500">Block reasons</p>{state?.block_reasons.length ? state.block_reasons.map((reason) => <p className="mt-1 text-sm text-red-300" key={reason}>{reason}</p>) : <p className="mt-1 text-emerald-300">None</p>}</Card>
    </section>
    <Card className="mt-5 overflow-x-auto"><h2 className="mb-3 font-medium">Risk decisions</h2><table className="w-full min-w-[900px] text-left text-sm"><thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Symbol</th><th>Strategy</th><th>Direction</th><th>Status</th><th>Risk budget</th><th>Quantity</th><th>Notional</th><th>Maximum loss</th><th>R:R</th><th>Rejections</th></tr></thead><tbody>{decisions.map((row) => <tr className="border-t border-slate-800" key={`${row.symbol}-${row.strategy}`}><td className="py-3"><Link className="text-cyan-300" href={`/risk/${encodeURIComponent(row.symbol)}`}>{row.symbol}</Link></td><td>{row.strategy.replaceAll("_", " ")}</td><td className="uppercase">{row.direction}</td><td className={row.allowed ? "text-emerald-300" : "text-red-300"}>{row.status.replaceAll("_", " ")}</td><td>{show(row.risk_amount)}</td><td>{show(row.position_quantity)}</td><td>{show(row.position_notional)}</td><td>{show(row.maximum_loss)}</td><td>{show(row.estimated_rr)}</td><td>{row.rejection_reasons.length}</td></tr>)}</tbody></table></Card>
  </main>;
}
