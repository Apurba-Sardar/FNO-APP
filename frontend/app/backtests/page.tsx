"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { BacktestChart } from "@/components/backtest-chart";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

type Point = { timestamp: string; equity: number; drawdown: number };
type Trade = { trade_id: string; exit_time: string; symbol: string; strategy: string; direction: string; opportunity_score: number; setup_score: number; entry: number; stop: number; target: number; exit: number; r_multiple: number; gross_pnl: number; fees: number; slippage: number; net_pnl: number; duration_minutes: number; exit_reason: string; factor_snapshot: unknown; risk_decision: unknown; maximum_favorable_excursion: number; maximum_adverse_excursion: number };
type Result = { backtest_id: string; status: string; performance: null | Record<string, number | null>; execution_metrics: null | Record<string, number | boolean>; counters: Record<string, number>; equity_curve: Point[]; trades: Trade[]; warnings: string[]; error: string | null };
const number = (value: unknown) => typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "—";

export default function BacktestsPage() {
  const now = new Date();
  const [symbol, setSymbol] = useState("B-BTC_USDT");
  const [start, setStart] = useState(new Date(now.getTime() - 24 * 3600_000).toISOString().slice(0, 16));
  const [end, setEnd] = useState(now.toISOString().slice(0, 16));
  const [equity, setEquity] = useState(100000);
  const [risk, setRisk] = useState(0.5);
  const [minScore, setMinScore] = useState(50);
  const [minSetup, setMinSetup] = useState(60);
  const [minRR, setMinRR] = useState(1.5);
  const [fee, setFee] = useState(0.05);
  const [slippage, setSlippage] = useState(5);
  const [execution, setExecution] = useState("market");
  const [result, setResult] = useState<Result | null>(null);
  const [runs, setRuns] = useState<Array<{ backtest_id: string; status: string; symbols: string[]; total_trades: number }>>([]);
  const [selected, setSelected] = useState<Trade | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loadRuns = () => { const api = getApiUrl(); fetch(`${api}/backtests`).then((response) => response.json()).then((body) => setRuns(body.items ?? [])).catch(() => undefined); };
  useEffect(() => { void loadRuns(); }, []);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(""); setResult(null);
    const configuration = {
      symbols: symbol.split(",").map((item) => item.trim()).filter(Boolean),
      start_timestamp: new Date(start).toISOString(), end_timestamp: new Date(end).toISOString(), initial_equity: equity,
      execution_model: execution, minimum_opportunity_score: minScore, minimum_setup_score: minSetup,
      fee_model: { maker_fee_percent: 0.02, taker_fee_percent: fee, use_taker: true },
      slippage_model: { kind: "fixed_bps", entry_slippage_bps: slippage, exit_slippage_bps: slippage, volatility_multiplier: 1 },
      risk: { risk_per_trade_percent: risk, minimum_risk_reward: minRR },
    };
    try {
      const api = getApiUrl();
      const created = await fetch(`${api}/backtests`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ configuration }) });
      if (!created.ok) throw new Error(await created.text());
      const record = await created.json();
      const response = await fetch(`${api}/backtests/${record.backtest_id}/run`, { method: "POST" });
      if (!response.ok) throw new Error(await response.text());
      setResult(await response.json()); await loadRuns();
    } catch (cause) { setError(String(cause)); } finally { setBusy(false); }
  }
  async function viewRun(identifier: string) {
    setError("");
    try {
      const api = getApiUrl();
      const response = await fetch(`${api}/backtests/${identifier}`);
      if (!response.ok) throw new Error(await response.text());
      setResult(await response.json()); setSelected(null);
    } catch (cause) { setError(String(cause)); }
  }
  const metrics = result?.performance;
  return <main className="mx-auto max-w-7xl p-4 sm:p-6">
    <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">Phase 8 · historical validation only</p>
    <div className="flex flex-wrap items-end justify-between gap-3"><div><h1 className="text-2xl font-semibold">Backtesting Lab</h1><p className="text-sm text-slate-400">Point-in-time strategy validation. Historical results do not guarantee future performance.</p></div><Link className="text-sm text-cyan-300" href="/">← Overview</Link></div>
    <form onSubmit={submit} className="mt-5 grid gap-3 rounded-xl border border-slate-800 bg-slate-950 p-4 sm:grid-cols-2 lg:grid-cols-4">
      <label className="text-xs text-slate-400">Symbols, comma separated<input className="mt-1 w-full rounded bg-slate-900 p-2 text-slate-100" value={symbol} onChange={(e) => setSymbol(e.target.value)} /></label>
      <label className="text-xs text-slate-400">Start UTC<input type="datetime-local" className="mt-1 w-full rounded bg-slate-900 p-2" value={start} onChange={(e) => setStart(e.target.value)} /></label>
      <label className="text-xs text-slate-400">End UTC<input type="datetime-local" className="mt-1 w-full rounded bg-slate-900 p-2" value={end} onChange={(e) => setEnd(e.target.value)} /></label>
      <label className="text-xs text-slate-400">Initial equity<input type="number" className="mt-1 w-full rounded bg-slate-900 p-2" value={equity} onChange={(e) => setEquity(+e.target.value)} /></label>
      <label className="text-xs text-slate-400">Risk %<input type="number" step="0.1" className="mt-1 w-full rounded bg-slate-900 p-2" value={risk} onChange={(e) => setRisk(+e.target.value)} /></label>
      <label className="text-xs text-slate-400">Opportunity score<input type="number" className="mt-1 w-full rounded bg-slate-900 p-2" value={minScore} onChange={(e) => setMinScore(+e.target.value)} /></label>
      <label className="text-xs text-slate-400">Setup score<input type="number" className="mt-1 w-full rounded bg-slate-900 p-2" value={minSetup} onChange={(e) => setMinSetup(+e.target.value)} /></label>
      <label className="text-xs text-slate-400">Minimum R:R<input type="number" step="0.25" className="mt-1 w-full rounded bg-slate-900 p-2" value={minRR} onChange={(e) => setMinRR(+e.target.value)} /></label>
      <label className="text-xs text-slate-400">Taker fee %<input type="number" step="0.01" className="mt-1 w-full rounded bg-slate-900 p-2" value={fee} onChange={(e) => setFee(+e.target.value)} /></label>
      <label className="text-xs text-slate-400">Slippage bps<input type="number" className="mt-1 w-full rounded bg-slate-900 p-2" value={slippage} onChange={(e) => setSlippage(+e.target.value)} /></label>
      <label className="text-xs text-slate-400">Execution<select className="mt-1 w-full rounded bg-slate-900 p-2" value={execution} onChange={(e) => setExecution(e.target.value)}><option value="market">Market</option><option value="limit">Limit</option><option value="breakout_trigger">Breakout trigger</option></select></label>
      <button disabled={busy} className="self-end rounded bg-cyan-500 p-2 font-semibold text-slate-950 disabled:opacity-50">{busy ? "Running historical simulation…" : "Create and run"}</button>
    </form>
    {error && <p className="mt-4 rounded bg-red-950 p-3 text-red-300">{error}</p>}
    {result && <>
      <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{[["Final equity", metrics?.final_equity], ["Net P&L", metrics?.net_pnl], ["Return %", metrics?.total_return_percent], ["Win rate %", metrics?.win_rate], ["Profit factor", metrics?.profit_factor], ["Expectancy", metrics?.expectancy], ["Max drawdown", metrics?.maximum_drawdown], ["Loss streak", metrics?.maximum_consecutive_losses], ["Trades", metrics?.trades], ["Fees", result.execution_metrics?.total_fees]].map(([label, value]) => <Card key={String(label)}><p className="text-xs text-slate-500">{label}</p><p className="mt-1 text-lg">{number(value)}</p></Card>)}</section>
      {result.error && <p className="mt-4 text-red-300">{result.error}</p>}
      <div className="mt-5 grid gap-4 lg:grid-cols-2"><Card><h2 className="mb-2 font-medium">Equity curve</h2><BacktestChart points={result.equity_curve} field="equity" /></Card><Card><h2 className="mb-2 font-medium">Drawdown curve</h2><BacktestChart points={result.equity_curve} field="drawdown" /></Card></div>
      <Card className="mt-5"><h2 className="font-medium">Validation warnings</h2>{result.warnings.map((warning) => <p className="mt-2 text-sm text-amber-300" key={warning}>⚠ {warning}</p>)}</Card>
      <Card className="mt-5 overflow-x-auto"><h2 className="mb-3 font-medium">Trades</h2><table className="w-full min-w-[1200px] text-left text-xs"><thead className="uppercase text-slate-500"><tr>{["Date", "Pair", "Strategy", "Direction", "Opp.", "Setup", "Entry", "Stop", "Target", "Exit", "R", "Gross", "Fees", "Slippage", "Net", "Duration", "Reason"].map((item) => <th className="p-2" key={item}>{item}</th>)}</tr></thead><tbody>{result.trades.map((trade) => <tr onClick={() => setSelected(trade)} className="cursor-pointer border-t border-slate-800 hover:bg-slate-900" key={trade.trade_id}><td className="p-2">{new Date(trade.exit_time).toLocaleString()}</td><td>{trade.symbol}</td><td>{trade.strategy}</td><td>{trade.direction}</td><td>{number(trade.opportunity_score)}</td><td>{number(trade.setup_score)}</td><td>{number(trade.entry)}</td><td>{number(trade.stop)}</td><td>{number(trade.target)}</td><td>{number(trade.exit)}</td><td>{number(trade.r_multiple)}</td><td>{number(trade.gross_pnl)}</td><td>{number(trade.fees)}</td><td>{number(trade.slippage)}</td><td>{number(trade.net_pnl)}</td><td>{number(trade.duration_minutes)}m</td><td>{trade.exit_reason}</td></tr>)}</tbody></table></Card>
      {selected && <Card className="mt-5"><div className="flex justify-between"><h2 className="font-medium">Trade audit · {selected.symbol}</h2><button onClick={() => setSelected(null)}>Close</button></div><p className="mt-2 text-sm text-slate-400">MFE {number(selected.maximum_favorable_excursion)} · MAE {number(selected.maximum_adverse_excursion)}</p><pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap text-xs text-slate-400">{JSON.stringify({ factors: selected.factor_snapshot, risk: selected.risk_decision }, null, 2)}</pre></Card>}
    </>}
    <Card className="mt-5"><h2 className="font-medium">Saved validation runs</h2>{runs.map((run) => <p className="mt-2 flex flex-wrap items-center gap-2 text-sm" key={run.backtest_id}><span>{run.status.toUpperCase()} · {run.symbols.join(", ")} · {run.total_trades} trades</span><button className="text-cyan-300" onClick={() => void viewRun(run.backtest_id)}>View results</button><a className="text-cyan-300" href={`${getApiUrl()}/backtests/${run.backtest_id}/report`} target="_blank">HTML report</a></p>)}</Card>
  </main>;
}
