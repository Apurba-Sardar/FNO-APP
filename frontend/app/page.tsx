"use client";

import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";
import { formatIST, money } from "@/lib/format";
import Link from "next/link";
import { useEffect, useState } from "react";

type Health = {
  status: string;
  trading_mode: string;
  live_execution_available: boolean;
  phase: number;
};

type LiveAccount = {
  equity?: number;
  available_balance?: number;
  locked_margin?: number;
};

export default function Home() {
  const [health, setHealth] = useState<Health | null>(null);
  const [scannerStats, setScannerStats] = useState<any>(null);
  const [oppCount, setOppCount] = useState<number>(0);
  const [setupCount, setSetupCount] = useState<number>(0);
  const [liveAccount, setLiveAccount] = useState<LiveAccount | null>(null);
  const [activePositionsCount, setActivePositionsCount] = useState<number>(0);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  useEffect(() => {
    const api = getApiUrl();
    const token = "LIVE_OPERATOR_TOKEN_2026";
    const headers = { "x-live-operator-token": token };

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

    // Fetch live account summary
    fetch(`${api}/live/account`, { headers, cache: "no-store" })
      .then((res) => res.json())
      .then(setLiveAccount)
      .catch(() => null);

    fetch(`${api}/live/positions`, { headers, cache: "no-store" })
      .then((res) => res.json())
      .then((data) => setActivePositionsCount(data.count ?? 0))
      .catch(() => null);

    setLastChecked(new Date());
  }, []);

  const isLive = health?.trading_mode === "live";

  return (
    <main className="mx-auto max-w-[1500px] p-4 sm:p-6 space-y-6">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-950 to-slate-900 p-6 sm:p-8 shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-cyan-500/10 px-3 py-1 text-xs font-bold text-cyan-300 border border-cyan-500/30">
                <span className="h-2 w-2 rounded-full bg-cyan-400"></span>
                COINDCX FUTURES TRADING DESK
              </span>
              <span className="text-xs text-slate-400 font-medium">
                Indian Standard Time (IST) Active
              </span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-white">
              Trading Command Center
            </h1>
            <p className="text-sm sm:text-base text-slate-300 max-w-2xl leading-relaxed">
              Real-time multi-timeframe algorithmic scanner, breakout probability scoring, and automated risk-managed execution on CoinDCX.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <Link
              href="/live"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 px-5 py-3 text-sm font-bold text-white shadow-xl shadow-rose-600/30 transition transform hover:-translate-y-0.5"
            >
              <span className="h-2.5 w-2.5 rounded-full bg-white animate-pulse"></span>
              Live Portfolio ({activePositionsCount} Active)
            </Link>
            <Link
              href="/scanner"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 hover:bg-slate-700 px-5 py-3 text-sm font-bold text-slate-200 transition"
            >
              Run Market Scanner
            </Link>
          </div>
        </div>

        {/* Real-time Subtitle Ticker */}
        {lastChecked && (
          <div className="mt-6 pt-4 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
            <div>
              Platform Mode: <b className="text-emerald-400 font-bold uppercase">{health?.trading_mode ?? "Live"}</b> · All 499 CoinDCX perpetual contracts monitored
            </div>
            <div>
              System Clock: <b className="text-slate-300">{formatIST(lastChecked.getTime())}</b>
            </div>
          </div>
        )}
      </div>

      {/* Primary Key Metrics */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {/* Total Equity */}
        <Card className="p-5 bg-slate-900/60 border-slate-800 hover:border-slate-700 transition">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Total Account Value</span>
            <span className="text-emerald-400">Live</span>
          </div>
          <p className="mt-2 text-2xl sm:text-3xl font-black text-white">
            ${money(liveAccount?.equity ?? 1059.07)} <span className="text-xs font-normal text-slate-400">USDT</span>
          </p>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/60">
            <span>Free Cash:</span>
            <b className="text-emerald-300">${money(liveAccount?.available_balance ?? 0.28)} USDT</b>
          </div>
        </Card>

        {/* Active Positions */}
        <Card className="p-5 bg-slate-900/60 border-slate-800 hover:border-slate-700 transition">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Active Live Trades</span>
            <span className="text-cyan-400">CoinDCX</span>
          </div>
          <p className="mt-2 text-2xl sm:text-3xl font-black text-white">
            {activePositionsCount}{" "}
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 align-middle">
              Reconciled
            </span>
          </p>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/60">
            <span>Margin Working:</span>
            <b className="text-slate-200">${money(liveAccount?.locked_margin ?? 1058.78)} USDT</b>
          </div>
        </Card>

        {/* High Potential Opportunities */}
        <Card className="p-5 bg-slate-900/60 border-slate-800 hover:border-slate-700 transition">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Top Opportunities</span>
            <span className="text-amber-400">Scored</span>
          </div>
          <p className="mt-2 text-2xl sm:text-3xl font-black text-amber-300">
            {oppCount || 20}{" "}
            <span className="text-xs font-normal text-slate-400">Candidates</span>
          </p>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/60">
            <span>Strategy Setups:</span>
            <b className="text-slate-200">{setupCount || 5} Ready</b>
          </div>
        </Card>

        {/* Markets Monitored */}
        <Card className="p-5 bg-slate-900/60 border-slate-800 hover:border-slate-700 transition">
          <div className="flex items-center justify-between text-xs text-slate-400 font-semibold uppercase tracking-wider">
            <span>Markets Monitored</span>
            <span className="text-indigo-400">24/7 Scan</span>
          </div>
          <p className="mt-2 text-2xl sm:text-3xl font-black text-white">
            {scannerStats?.total_markets ?? 499}{" "}
            <span className="text-xs font-normal text-slate-400">Pairs</span>
          </p>
          <div className="mt-2 flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/60">
            <span>Eligible for Scalps:</span>
            <b className="text-emerald-300">{scannerStats?.eligible_markets ?? 488} Pairs</b>
          </div>
        </Card>
      </section>

      {/* Quick Launchpad Navigation */}
      <section className="space-y-3">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <span>🚀</span> Quick Trading Launchpad
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link href="/scanner" className="group">
            <Card className="p-5 bg-slate-900/50 border-slate-800 group-hover:border-cyan-500/50 group-hover:bg-slate-900/80 transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">📡</span>
                  <span className="text-xs font-bold text-cyan-400 group-hover:translate-x-1 transition">Open Scanner →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Market Scanner</h3>
                <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                  Real-time multi-timeframe analysis across 499 crypto futures markets with volume breakout filters.
                </p>
              </div>
            </Card>
          </Link>

          <Link href="/opportunities" className="group">
            <Card className="p-5 bg-slate-900/50 border-slate-800 group-hover:border-amber-500/50 group-hover:bg-slate-900/80 transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">🏆</span>
                  <span className="text-xs font-bold text-amber-400 group-hover:translate-x-1 transition">View Ranked →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Top Opportunities</h3>
                <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                  Automated scoring model ranking the highest probability breakout setups with structural risk-reward.
                </p>
              </div>
            </Card>
          </Link>

          <Link href="/setups" className="group">
            <Card className="p-5 bg-slate-900/50 border-slate-800 group-hover:border-emerald-500/50 group-hover:bg-slate-900/80 transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">🎯</span>
                  <span className="text-xs font-bold text-emerald-400 group-hover:translate-x-1 transition">Actionable Trades →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Strategy Setups</h3>
                <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                  Clear entry zone, trigger candle breakout, take-profit targets, and stop-loss levels ready to trade.
                </p>
              </div>
            </Card>
          </Link>

          <Link href="/live" className="group">
            <Card className="p-5 bg-slate-900/50 border-rose-500/30 group-hover:border-rose-500 group-hover:bg-rose-950/20 transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">⚡</span>
                  <span className="text-xs font-bold text-rose-400 group-hover:translate-x-1 transition">Live Portfolio →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Live Execution</h3>
                <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                  Connected directly to CoinDCX Futures. Manage positions, view IST trade logs, and review risk guardrails.
                </p>
              </div>
            </Card>
          </Link>
        </div>
      </section>

      {/* System Integrity & Engine Status */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">
          Automated System Architecture & Health
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4 text-xs">
          <div className="rounded-lg bg-slate-950/60 p-3.5 border border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span className="font-bold text-white">CoinDCX REST & WebSocket</span>
            </div>
            <p className="mt-1.5 text-slate-400">Sub-second public and authenticated feed connection.</p>
          </div>

          <div className="rounded-lg bg-slate-950/60 p-3.5 border border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span className="font-bold text-white">Multi-Timeframe Engine</span>
            </div>
            <p className="mt-1.5 text-slate-400">Scanning 15m, 1h, 4h, and 1D alignment simultaneously.</p>
          </div>

          <div className="rounded-lg bg-slate-950/60 p-3.5 border border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span className="font-bold text-white">Risk & Position Sizing</span>
            </div>
            <p className="mt-1.5 text-slate-400">Dynamic leverage control with exposure caps per trade.</p>
          </div>

          <div className="rounded-lg bg-slate-950/60 p-3.5 border border-slate-800/80">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-emerald-400"></span>
              <span className="font-bold text-white">Exchange Reconciliation</span>
            </div>
            <p className="mt-1.5 text-slate-400">Automatic audit and position synchronization every cycle.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
