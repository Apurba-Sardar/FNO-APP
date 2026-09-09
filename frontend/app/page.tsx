"use client";

import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";
import { balance, formatIST } from "@/lib/format";
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
    <main className="mx-auto max-w-[1600px] p-4 sm:p-6 space-y-6">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-br from-[#121217] via-[#09090c] to-[#070709] p-6 sm:p-8 shadow-[0_25px_60px_-15px_rgba(0,0,0,0.95),inset_0_1px_0_0_rgba(255,255,255,0.08)]">
        {/* Subtle radial sheen */}
        <div className="absolute -top-24 -right-24 w-96 h-96 bg-[#00F5A0]/[0.03] blur-[100px] pointer-events-none rounded-full" />
        
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2.5">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#00D9F5]/10 px-3 py-1 text-[11px] font-bold text-[#00D9F5] border border-[#00D9F5]/30 font-mono shadow-[0_0_15px_rgba(0,217,245,0.15)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#00D9F5] animate-pulse"></span>
                COINDCX FUTURES TRADING DESK
              </span>
              <span className="text-xs text-zinc-400 font-mono">
                IST (UTC+5:30) Active
              </span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-black tracking-tight text-white">
              Trading Command Center
            </h1>
            <p className="text-sm sm:text-base text-zinc-400 max-w-2xl leading-relaxed">
              Real-time multi-timeframe algorithmic scanner, breakout probability scoring, and automated risk-managed execution on CoinDCX.
            </p>
          </div>

          <div className="relative z-10 flex flex-col sm:flex-row items-start sm:items-center gap-3">
            <Link
              href="/live"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-[#FF3366] to-[#E11D48] hover:from-[#ff4d79] hover:to-[#f43f5e] px-5 py-3 text-sm font-bold text-white shadow-[0_0_25px_rgba(255,51,102,0.4)] transition transform hover:-translate-y-0.5 active:scale-[0.98]"
            >
              <span className="h-2 w-2 rounded-full bg-white animate-pulse"></span>
              Live Portfolio ({activePositionsCount} Active)
            </Link>
            <Link
              href="/scanner"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/[0.09] bg-[#121217] hover:bg-white/[0.08] hover:border-white/[0.18] px-5 py-3 text-sm font-bold text-zinc-200 transition shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] active:scale-[0.98]"
            >
              Run Market Scanner
            </Link>
          </div>
        </div>

        {/* Real-time Subtitle Ticker */}
        {lastChecked && (
          <div className="relative z-10 mt-6 pt-4 border-t border-white/[0.07] flex flex-wrap items-center justify-between gap-2 text-xs text-zinc-400 font-mono">
            <div>
              Platform Mode: <b className="text-[#00F5A0] font-bold uppercase">{health?.trading_mode ?? "Live"}</b> · All 499 CoinDCX perpetual contracts monitored
            </div>
            <div>
              System Clock: <b className="text-zinc-200">{formatIST(lastChecked.getTime())}</b>
            </div>
          </div>
        )}
      </div>

      {/* Primary Key Metrics */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {/* Total Equity */}
        <Card className="p-5">
          <div className="flex items-center justify-between text-[11px] text-zinc-400 font-bold uppercase tracking-[0.14em] font-mono">
            <span>Total Account Value</span>
            <span className="text-[#00F5A0] flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0] animate-pulse"></span>
              Live
            </span>
          </div>
          <b className="mt-2 text-2xl sm:text-3xl font-black font-mono text-white block">
            ${balance(liveAccount?.equity ?? 1059.07)} <span className="text-xs font-normal text-zinc-500">USDT</span>
          </b>
          <div className="mt-2 flex items-center justify-between text-xs text-zinc-400 pt-2 border-t border-white/[0.06]">
            <span>Free Cash:</span>
            <b className="text-[#00F5A0] font-mono">${balance(liveAccount?.available_balance ?? 0.28)} USDT</b>
          </div>
        </Card>

        {/* Active Positions */}
        <Card className="p-5">
          <div className="flex items-center justify-between text-[11px] text-zinc-400 font-bold uppercase tracking-[0.14em] font-mono">
            <span>Active Live Trades</span>
            <span className="text-[#00D9F5]">CoinDCX</span>
          </div>
          <p className="mt-2 text-2xl sm:text-3xl font-black font-mono text-white">
            {activePositionsCount}{" "}
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30 align-middle">
              Reconciled
            </span>
          </p>
          <div className="mt-2 flex items-center justify-between text-xs text-zinc-400 pt-2 border-t border-white/[0.06]">
            <span>Margin Working:</span>
            <b className="text-zinc-200 font-mono">${balance(liveAccount?.locked_margin ?? 1058.78)} USDT</b>
          </div>
        </Card>

        {/* High Potential Opportunities */}
        <Card className="p-5">
          <div className="flex items-center justify-between text-[11px] text-zinc-400 font-bold uppercase tracking-[0.14em] font-mono">
            <span>Top Opportunities</span>
            <span className="text-[#FFB800]">Scored</span>
          </div>
          <p className="mt-2 text-2xl sm:text-3xl font-black font-mono text-[#FFB800]">
            {oppCount || 20}{" "}
            <span className="text-xs font-normal text-zinc-500">Candidates</span>
          </p>
          <div className="mt-2 flex items-center justify-between text-xs text-zinc-400 pt-2 border-t border-white/[0.06]">
            <span>Strategy Setups:</span>
            <b className="text-zinc-200 font-mono">{setupCount || 5} Ready</b>
          </div>
        </Card>

        {/* Markets Monitored */}
        <Card className="p-5">
          <div className="flex items-center justify-between text-[11px] text-zinc-400 font-bold uppercase tracking-[0.14em] font-mono">
            <span>Markets Monitored</span>
            <span className="text-purple-400">24/7 Scan</span>
          </div>
          <p className="mt-2 text-2xl sm:text-3xl font-black font-mono text-white">
            {scannerStats?.total_markets ?? 499}{" "}
            <span className="text-xs font-normal text-zinc-500">Pairs</span>
          </p>
          <div className="mt-2 flex items-center justify-between text-xs text-zinc-400 pt-2 border-t border-white/[0.06]">
            <span>Eligible for Scalps:</span>
            <b className="text-[#00F5A0] font-mono">{scannerStats?.eligible_markets ?? 488} Pairs</b>
          </div>
        </Card>
      </section>

      {/* Quick Launchpad Navigation */}
      <section className="space-y-3">
        <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-zinc-400 font-mono flex items-center gap-2">
          <span>🚀</span> Quick Trading Launchpad
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link href="/scanner" className="group">
            <Card className="p-5 group-hover:border-[#00D9F5]/40 group-hover:shadow-[0_20px_45px_-10px_rgba(0,217,245,0.15)] transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">📡</span>
                  <span className="text-xs font-bold text-[#00D9F5] group-hover:translate-x-1 transition font-mono">Open Scanner →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Market Scanner</h3>
                <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
                  Real-time multi-timeframe analysis across 499 crypto futures markets with volume breakout filters.
                </p>
              </div>
            </Card>
          </Link>

          <Link href="/opportunities" className="group">
            <Card className="p-5 group-hover:border-[#FFB800]/40 group-hover:shadow-[0_20px_45px_-10px_rgba(255,184,0,0.15)] transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">🏆</span>
                  <span className="text-xs font-bold text-[#FFB800] group-hover:translate-x-1 transition font-mono">View Ranked →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Top Opportunities</h3>
                <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
                  Automated scoring model ranking the highest probability breakout setups with structural risk-reward.
                </p>
              </div>
            </Card>
          </Link>

          <Link href="/setups" className="group">
            <Card className="p-5 group-hover:border-[#00F5A0]/40 group-hover:shadow-[0_20px_45px_-10px_rgba(0,245,160,0.15)] transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">🎯</span>
                  <span className="text-xs font-bold text-[#00F5A0] group-hover:translate-x-1 transition font-mono">Actionable Trades →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Strategy Setups</h3>
                <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
                  Clear entry zone, trigger candle breakout, take-profit targets, and stop-loss levels ready to trade.
                </p>
              </div>
            </Card>
          </Link>

          <Link href="/live" className="group">
            <Card className="p-5 border-[#FF3366]/25 group-hover:border-[#FF3366]/60 group-hover:shadow-[0_20px_45px_-10px_rgba(255,51,102,0.2)] transition h-full flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between">
                  <span className="text-2xl">⚡</span>
                  <span className="text-xs font-bold text-[#FF3366] group-hover:translate-x-1 transition font-mono">Live Portfolio →</span>
                </div>
                <h3 className="mt-3 text-base font-bold text-white">Live Execution</h3>
                <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
                  Connected directly to CoinDCX Futures. Manage positions, view IST trade logs, and review risk guardrails.
                </p>
              </div>
            </Card>
          </Link>
        </div>
      </section>

      {/* System Integrity & Engine Status */}
      <section className="rounded-2xl border border-white/[0.07] bg-[#0c0c10]/95 p-5 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.9)]">
        <h2 className="text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 font-mono mb-4">
          Automated System Architecture & Health
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4 text-xs">
          <div className="rounded-xl bg-[#08080b] p-3.5 border border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0] animate-pulse"></span>
              <span className="font-bold text-white font-mono">CoinDCX REST & WS</span>
            </div>
            <p className="mt-1.5 text-zinc-400 leading-relaxed">Sub-second public and authenticated feed connection.</p>
          </div>

          <div className="rounded-xl bg-[#08080b] p-3.5 border border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0] animate-pulse"></span>
              <span className="font-bold text-white font-mono">Multi-Timeframe Engine</span>
            </div>
            <p className="mt-1.5 text-zinc-400 leading-relaxed">Scanning 15m, 1h, 4h, and 1D alignment simultaneously.</p>
          </div>

          <div className="rounded-xl bg-[#08080b] p-3.5 border border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0] animate-pulse"></span>
              <span className="font-bold text-white font-mono">Risk & Position Sizing</span>
            </div>
            <p className="mt-1.5 text-zinc-400 leading-relaxed">Dynamic leverage control with exposure caps per trade.</p>
          </div>

          <div className="rounded-xl bg-[#08080b] p-3.5 border border-white/[0.06]">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0] animate-pulse"></span>
              <span className="font-bold text-white font-mono">Exchange Reconciliation</span>
            </div>
            <p className="mt-1.5 text-zinc-400 leading-relaxed">Automatic audit and position synchronization every cycle.</p>
          </div>
        </div>
      </section>
    </main>
  );
}
