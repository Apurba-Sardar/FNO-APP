"use client";

import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";
import Link from "next/link";
import { useEffect, useState } from "react";

type Health = {
  status: string;
  trading_mode: string;
  live_execution_available: boolean;
  phase: number;
};

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [scannerStats, setScannerStats] = useState<any>(null);
  const [oppCount, setOppCount] = useState<number>(0);
  const [setupCount, setSetupCount] = useState<number>(0);

  useEffect(() => {
    const api = getApiUrl();
    fetch(`${api}/health`, { cache: "no-store" })
      .then((res) => res.json())
      .then(setHealth)
      .catch(() => null);

    fetch(`${api}/scanner/status`, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setScannerStats(data.stats))
      .catch(() => null);

    fetch(`${api}/opportunities/top`, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setOppCount(data.count ?? 0))
      .catch(() => null);

    fetch(`${api}/setups?limit=500`, { cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setSetupCount(data.count ?? 0))
      .catch(() => null);
  }, []);

  const isLive = health?.trading_mode === "live";

  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6">
      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">
            CoinDCX USDT Futures
          </p>
          <h1 className="text-3xl font-black text-slate-100">
            Algorithmic Trading & Scanner Suite
          </h1>
        </div>
        <div className="flex gap-2">
          <span
            className={`w-fit rounded-full border px-3.5 py-1 text-xs font-bold uppercase tracking-wider ${
              isLive
                ? "border-rose-500/50 bg-rose-500/20 text-rose-300"
                : "border-amber-500/40 bg-amber-500/10 text-amber-300"
            }`}
          >
            {isLive ? "LIVE MODE ACTIVE" : "PAPER SIMULATION MODE"}
          </span>
        </div>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border-cyan-500/20 bg-cyan-950/20">
          <p className="text-xs font-semibold uppercase text-slate-400">Trading Mode</p>
          <p className={`mt-2 text-2xl font-black uppercase ${isLive ? "text-rose-400" : "text-amber-400"}`}>
            {health?.trading_mode ?? "Paper"}
          </p>
        </Card>
        <Card className="border-emerald-500/20 bg-emerald-950/20">
          <p className="text-xs font-semibold uppercase text-slate-400">API Health</p>
          <p className="mt-2 text-2xl font-black text-emerald-400 uppercase">
            {health?.status === "ok" ? "HEALTHY & CONNECTED" : "OFFLINE"}
          </p>
        </Card>
        <Card className="border-purple-500/20 bg-purple-950/20">
          <p className="text-xs font-semibold uppercase text-slate-400">Live Execution</p>
          <p className={`mt-2 text-2xl font-black ${health?.live_execution_available ? "text-emerald-400" : "text-slate-400"}`}>
            {health?.live_execution_available ? "ENABLED" : "CONFIGURED"}
          </p>
        </Card>
        <Card className="border-amber-500/20 bg-amber-950/20">
          <p className="text-xs font-semibold uppercase text-slate-400">System Phase</p>
          <p className="mt-2 text-2xl font-black text-amber-300">Phase 10 Engine</p>
        </Card>
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-slate-100">Live Trading Hub</h2>
              <span className="rounded bg-rose-500/20 px-2 py-0.5 text-xs font-bold text-rose-300">REAL MONEY</span>
            </div>
            <p className="mt-2 text-sm text-slate-400">
              Track live account equity, margins, 5 open positions, active exit orders, and interactive TradingView charts.
            </p>
          </div>
          <Link
            className="mt-4 inline-flex items-center justify-center rounded-lg bg-rose-600 py-2.5 text-sm font-black text-white hover:bg-rose-500 transition"
            href="/live"
          >
            Open Live Trading Dashboard →
          </Link>
        </Card>

        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-slate-100">Market Scanner</h2>
              <span className="rounded bg-cyan-500/20 px-2 py-0.5 text-xs font-bold text-cyan-300">24/7 ACTIVE</span>
            </div>
            <p className="mt-2 text-sm text-slate-400">
              Multi-timeframe automated futures candidate discovery and trend analysis.
            </p>
            <div className="mt-3 text-xs text-slate-300">
              Markets Scanned: <b>{scannerStats?.total_markets ?? 0}</b> · Eligible: <b>{scannerStats?.eligible_markets ?? 0}</b>
            </div>
          </div>
          <Link
            className="mt-4 inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-900 py-2 text-sm font-bold text-slate-200 hover:bg-slate-800 transition"
            href="/scanner"
          >
            View All-Market Scanner →
          </Link>
        </Card>

        <Card className="flex flex-col justify-between">
          <div>
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-bold text-slate-100">Ranked Opportunities</h2>
              <span className="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-bold text-amber-300">{oppCount} TOP SETUPS</span>
            </div>
            <p className="mt-2 text-sm text-slate-400">
              0–100 scored opportunities evaluated by structural risk:reward, volume expansion, and liquidity.
            </p>
          </div>
          <Link
            className="mt-4 inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-900 py-2 text-sm font-bold text-slate-200 hover:bg-slate-800 transition"
            href="/opportunities"
          >
            View Ranked Opportunities →
          </Link>
        </Card>

        <Card className="flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Strategy Setups ({setupCount})</h2>
            <p className="mt-2 text-sm text-slate-400">
              Deterministic trend-pullback & breakout setup monitoring with precise entry zones, stop loss, and target levels.
            </p>
          </div>
          <Link
            className="mt-4 inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-900 py-2 text-sm font-bold text-slate-200 hover:bg-slate-800 transition"
            href="/setups"
          >
            View Strategy Setups →
          </Link>
        </Card>

        <Card className="flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Risk Management Center</h2>
            <p className="mt-2 text-sm text-slate-400">
              Hard pre-score market filters, max daily loss gates, position limits, and slippage buffer controls.
            </p>
          </div>
          <Link
            className="mt-4 inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-900 py-2 text-sm font-bold text-slate-200 hover:bg-slate-800 transition"
            href="/risk"
          >
            Open Risk Center →
          </Link>
        </Card>

        <Card className="flex flex-col justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-100">Paper Trading & Backtesting</h2>
            <p className="mt-2 text-sm text-slate-400">
              Simulated paper execution engine with historical backtest lab and equity curve analytics.
            </p>
          </div>
          <div className="mt-4 flex gap-2">
            <Link
              className="flex-1 text-center rounded-lg bg-amber-400 py-2 text-sm font-bold text-slate-950 hover:bg-amber-300 transition"
              href="/paper"
            >
              Paper Mode
            </Link>
            <Link
              className="flex-1 text-center rounded-lg border border-slate-700 bg-slate-900 py-2 text-sm font-bold text-slate-200 hover:bg-slate-800 transition"
              href="/backtests"
            >
              Backtests
            </Link>
          </div>
        </Card>
      </section>
    </main>
  );
}
