"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { BacktestChart } from "@/components/backtest-chart";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

type Point = { timestamp: string; equity: number; drawdown: number };
type Trade = {
  trade_id: string;
  exit_time: string;
  symbol: string;
  strategy: string;
  direction: string;
  opportunity_score: number;
  setup_score: number;
  entry: number;
  stop: number;
  target: number;
  exit: number;
  r_multiple: number;
  gross_pnl: number;
  fees: number;
  slippage: number;
  net_pnl: number;
  duration_minutes: number;
  exit_reason: string;
  factor_snapshot: unknown;
  risk_decision: unknown;
  maximum_favorable_excursion: number;
  maximum_adverse_excursion: number;
};
type Result = {
  backtest_id: string;
  status: string;
  performance: null | Record<string, number | null>;
  execution_metrics: null | Record<string, number | boolean>;
  counters: Record<string, number>;
  equity_curve: Point[];
  trades: Trade[];
  warnings: string[];
  error: string | null;
};

const number = (value: unknown) => (typeof value === "number" ? value.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "—");

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

  const loadRuns = () => {
    const api = getApiUrl();
    fetch(`${api}/backtests`)
      .then((response) => response.json())
      .then((body) => setRuns(body.items ?? []))
      .catch(() => undefined);
  };

  useEffect(() => {
    void loadRuns();
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    const configuration = {
      symbols: symbol.split(",").map((item) => item.trim()).filter(Boolean),
      start_timestamp: new Date(start).toISOString(),
      end_timestamp: new Date(end).toISOString(),
      initial_equity: equity,
      execution_model: execution,
      minimum_opportunity_score: minScore,
      minimum_setup_score: minSetup,
      fee_model: { maker_fee_percent: 0.02, taker_fee_percent: fee, use_taker: true },
      slippage_model: { kind: "fixed_bps", entry_slippage_bps: slippage, exit_slippage_bps: slippage, volatility_multiplier: 1 },
      risk: { risk_per_trade_percent: risk, minimum_risk_reward: minRR },
    };
    try {
      const api = getApiUrl();
      const created = await fetch(`${api}/backtests`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ configuration }),
      });
      if (!created.ok) throw new Error(await created.text());
      const record = await created.json();
      const response = await fetch(`${api}/backtests/${record.backtest_id}/run`, { method: "POST" });
      if (!response.ok) throw new Error(await response.text());
      setResult(await response.json());
      await loadRuns();
    } catch (cause) {
      setError(String(cause));
    } finally {
      setBusy(false);
    }
  }

  async function viewRun(identifier: string) {
    setError("");
    try {
      const api = getApiUrl();
      const response = await fetch(`${api}/backtests/${identifier}`);
      if (!response.ok) throw new Error(await response.text());
      setResult(await response.json());
      setSelected(null);
    } catch (cause) {
      setError(String(cause));
    }
  }

  const metrics = result?.performance;

  return (
    <main className="mx-auto max-w-[1600px] p-4 sm:p-8 space-y-7">
      {/* Header Banner - CRED Velvet Matte Obsidian */}
      <header className="cred-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.9)]">
        {/* Subtle Ambient Radial Glows */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-[#00D9F5]/10 blur-3xl"></div>
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-purple-500/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#00D9F5]/10 px-3 py-1 text-[11px] font-black tracking-wider uppercase text-[#00D9F5] border border-[#00D9F5]/30 shadow-[0_0_15px_rgba(0,217,245,0.2)]">
                <span>🔬</span> Quantitative Validation Engine
              </span>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                Point-In-Time Historical Simulation
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Backtesting & Strategy Lab
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              Validate strategy breakout parameters, fee friction, slippage models, and historical risk-reward profiles.
            </p>
          </div>

          <Link
            href="/"
            className="cred-btn-secondary rounded-xl px-4 py-2.5 text-xs font-bold text-slate-300 self-start lg:self-auto"
          >
            ← Back to Overview
          </Link>
        </div>
      </header>

      {/* Backtest Configuration Form */}
      <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
        <h2 className="text-base font-black text-white tracking-tight mb-4 flex items-center gap-2">
          <span>⚙️</span> Simulation Parameters
        </h2>

        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-xs">
          <label className="text-slate-400 font-medium">
            Symbols (comma separated)
            <input
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Start Time (UTC)
            <input
              type="datetime-local"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            End Time (UTC)
            <input
              type="datetime-local"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Initial Equity ($)
            <input
              type="number"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={equity}
              onChange={(e) => setEquity(+e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Risk % Per Trade
            <input
              type="number"
              step="0.1"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={risk}
              onChange={(e) => setRisk(+e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Min Opportunity Score
            <input
              type="number"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={minScore}
              onChange={(e) => setMinScore(+e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Min Setup Score
            <input
              type="number"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={minSetup}
              onChange={(e) => setMinSetup(+e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Min Risk:Reward
            <input
              type="number"
              step="0.25"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={minRR}
              onChange={(e) => setMinRR(+e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Taker Fee %
            <input
              type="number"
              step="0.01"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={fee}
              onChange={(e) => setFee(+e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Slippage (bps)
            <input
              type="number"
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={slippage}
              onChange={(e) => setSlippage(+e.target.value)}
            />
          </label>

          <label className="text-slate-400 font-medium">
            Execution Model
            <select
              className="mt-1.5 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-white font-mono focus:border-[#00D9F5] focus:outline-none focus:ring-1 focus:ring-[#00D9F5]/30 transition"
              value={execution}
              onChange={(e) => setExecution(e.target.value)}
            >
              <option value="market">Market Execution</option>
              <option value="limit">Limit Execution</option>
              <option value="breakout_trigger">Breakout Trigger</option>
            </select>
          </label>

          <button
            disabled={busy}
            className="self-end cred-btn-primary rounded-xl px-5 py-2.5 text-xs font-black flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {busy ? (
              <>
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-black border-t-transparent"></span>
                Simulating Historical Runs...
              </>
            ) : (
              "Run Backtest Simulation"
            )}
          </button>
        </form>
      </Card>

      {error && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs font-semibold text-rose-300 shadow-lg">
          ⚠️ {error}
        </div>
      )}

      {result && (
        <>
          {/* Metrics Grid */}
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["Final Equity", metrics?.final_equity],
              ["Net P&L", metrics?.net_pnl],
              ["Return %", metrics?.total_return_percent],
              ["Win Rate %", metrics?.win_rate],
              ["Profit Factor", metrics?.profit_factor],
              ["Expectancy", metrics?.expectancy],
              ["Max Drawdown", metrics?.maximum_drawdown],
              ["Loss Streak", metrics?.maximum_consecutive_losses],
              ["Trades", metrics?.trades],
              ["Total Fees", result.execution_metrics?.total_fees],
            ].map(([label, value]) => (
              <Card key={String(label)} className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{label}</p>
                <p className="mt-2 text-xl font-black text-white font-mono tracking-tight">{number(value)}</p>
              </Card>
            ))}
          </section>

          {result.error && (
            <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs font-bold text-rose-300">
              {result.error}
            </div>
          )}

          {/* Curves */}
          <div className="grid gap-5 lg:grid-cols-2">
            <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
              <h2 className="text-base font-black text-white tracking-tight mb-4">Simulated Equity Curve</h2>
              <BacktestChart points={result.equity_curve} field="equity" />
            </Card>
            <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
              <h2 className="text-base font-black text-white tracking-tight mb-4">Historical Drawdown Curve</h2>
              <BacktestChart points={result.equity_curve} field="drawdown" />
            </Card>
          </div>

          {result.warnings?.length > 0 && (
            <Card className="p-5 rounded-2xl border border-amber-500/30 bg-amber-950/20 shadow-xl">
              <h2 className="text-xs font-black text-amber-300 uppercase tracking-wider mb-2">Validation Warnings</h2>
              {result.warnings.map((warning) => (
                <p className="text-xs text-amber-200/80 mt-1" key={warning}>
                  ⚠ {warning}
                </p>
              ))}
            </Card>
          )}

          {/* Backtest Trades Table */}
          <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl overflow-hidden">
            <h2 className="text-base font-black text-white tracking-tight mb-4">Simulated Trade Executions</h2>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1200px] text-left text-xs">
                <thead>
                  <tr className="border-b border-white/[0.07] text-[10px] font-black uppercase tracking-[0.15em] text-slate-500">
                    {[
                      "Date",
                      "Pair",
                      "Strategy",
                      "Direction",
                      "Opp.",
                      "Setup",
                      "Entry",
                      "Stop",
                      "Target",
                      "Exit",
                      "R",
                      "Gross",
                      "Fees",
                      "Slippage",
                      "Net",
                      "Duration",
                      "Reason",
                    ].map((item) => (
                      <th className="py-3 px-2.5" key={item}>
                        {item}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {result.trades.map((trade) => (
                    <tr
                      onClick={() => setSelected(trade)}
                      className="cursor-pointer hover:bg-white/[0.04] transition-colors"
                      key={trade.trade_id}
                    >
                      <td className="py-2.5 px-2.5 font-mono text-slate-400">{new Date(trade.exit_time).toLocaleString()}</td>
                      <td className="py-2.5 px-2.5 font-bold text-white">{trade.symbol}</td>
                      <td className="py-2.5 px-2.5 text-slate-300 capitalize">{trade.strategy}</td>
                      <td className="py-2.5 px-2.5">
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-black uppercase ${
                            trade.direction.toLowerCase() === "long" ? "text-[#00F5A0]" : "text-[#FF3366]"
                          }`}
                        >
                          {trade.direction}
                        </span>
                      </td>
                      <td className="py-2.5 px-2.5 font-mono">{number(trade.opportunity_score)}</td>
                      <td className="py-2.5 px-2.5 font-mono">{number(trade.setup_score)}</td>
                      <td className="py-2.5 px-2.5 font-mono">${number(trade.entry)}</td>
                      <td className="py-2.5 px-2.5 font-mono text-[#FF3366]">${number(trade.stop)}</td>
                      <td className="py-2.5 px-2.5 font-mono text-[#00F5A0]">${number(trade.target)}</td>
                      <td className="py-2.5 px-2.5 font-mono">${number(trade.exit)}</td>
                      <td className="py-2.5 px-2.5 font-mono text-[#00D9F5]">{number(trade.r_multiple)}R</td>
                      <td className="py-2.5 px-2.5 font-mono">${number(trade.gross_pnl)}</td>
                      <td className="py-2.5 px-2.5 font-mono text-slate-400">${number(trade.fees)}</td>
                      <td className="py-2.5 px-2.5 font-mono text-slate-400">${number(trade.slippage)}</td>
                      <td className={`py-2.5 px-2.5 font-mono font-bold ${trade.net_pnl >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                        ${number(trade.net_pnl)}
                      </td>
                      <td className="py-2.5 px-2.5 font-mono text-slate-400">{number(trade.duration_minutes)}m</td>
                      <td className="py-2.5 px-2.5 text-slate-400">{trade.exit_reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {selected && (
            <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
              <div className="flex justify-between items-center">
                <h2 className="text-base font-black text-white">Trade Audit · {selected.symbol}</h2>
                <button
                  onClick={() => setSelected(null)}
                  className="cred-btn-secondary px-3 py-1 rounded-lg text-xs"
                >
                  Close
                </button>
              </div>
              <p className="mt-2 text-xs text-slate-400 font-mono">
                MFE {number(selected.maximum_favorable_excursion)} · MAE {number(selected.maximum_adverse_excursion)}
              </p>
              <pre className="mt-3 max-h-96 overflow-auto rounded-xl bg-[#060608] p-4 text-xs font-mono text-slate-300 border border-white/[0.05]">
                {JSON.stringify({ factors: selected.factor_snapshot, risk: selected.risk_decision }, null, 2)}
              </pre>
            </Card>
          )}
        </>
      )}

      {/* Saved Validation Runs */}
      <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
        <h2 className="text-base font-black text-white tracking-tight mb-3">Saved Validation Runs</h2>
        <div className="space-y-2">
          {runs.map((run) => (
            <div
              className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/[0.04] hover:border-white/[0.1] transition"
              key={run.backtest_id}
            >
              <span className="text-xs font-mono text-slate-300">
                <b className="text-[#00F5A0]">{run.status.toUpperCase()}</b> · {run.symbols.join(", ")} · {run.total_trades} trades
              </span>
              <div className="flex items-center gap-3 text-xs">
                <button
                  className="text-[#00D9F5] hover:text-white font-bold transition"
                  onClick={() => void viewRun(run.backtest_id)}
                >
                  View Results
                </button>
                <a
                  className="text-slate-400 hover:text-white transition"
                  href={`${getApiUrl()}/backtests/${run.backtest_id}/report`}
                  target="_blank"
                >
                  HTML Report ↗
                </a>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </main>
  );
}
