"use client";

import { Card } from "@/components/ui/card";
import { PaperChart } from "@/components/paper-chart";
import { getApiUrl } from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";

type AnyRow = Record<string, any>;
type ChartPoint = { timestamp: string; [key: string]: string | number };
const money = (value: unknown) => Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

export default function PaperPage() {
  const [status, setStatus] = useState<AnyRow>({});
  const [account, setAccount] = useState<AnyRow>({});
  const [positions, setPositions] = useState<AnyRow[]>([]);
  const [trades, setTrades] = useState<AnyRow[]>([]);
  const [orders, setOrders] = useState<AnyRow[]>([]);
  const [dailyReport, setDailyReport] = useState<AnyRow[]>([]);
  const [performance, setPerformance] = useState<AnyRow>({});
  const [curve, setCurve] = useState<ChartPoint[]>([]);
  const [health, setHealth] = useState<AnyRow>({});
  const [message, setMessage] = useState("");
  const [resetArmed, setResetArmed] = useState(false);
  const [showAllKpis, setShowAllKpis] = useState(false);

  const load = useCallback(async () => {
    try {
      const api = getApiUrl();
      const [s, a, p, t, o, d, perf, eq, h] = await Promise.all(
        ["status", "account", "positions?open_only=true", "trades", "orders", "daily-report", "performance", "equity", "health"].map((path) =>
          fetch(`${api}/paper/${path}`, { cache: "no-store" }).then((r) => r.json())
        )
      );
      setStatus(s);
      setAccount(a);
      setPositions(p.items ?? []);
      setTrades(t.items ?? []);
      setOrders(o.items ?? []);
      setDailyReport(d.items ?? []);
      setPerformance(perf);
      setCurve((eq.items ?? []) as ChartPoint[]);
      setHealth(h);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Paper API unavailable");
    }
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  }, [load]);

  const action = async (path: string) => {
    const api = getApiUrl();
    const response = await fetch(`${api}/paper/${path}`, { method: "POST" });
    const body = await response.json();
    setMessage(response.ok ? `${path.split("?")[0]} completed` : body.detail ?? "Request failed");
    await load();
  };

  const metrics = performance.metrics ?? {};
  const daily = useMemo(() => {
    if (dailyReport.length) {
      return dailyReport.map((row) => ({ timestamp: `${row.date}T00:00:00Z`, daily_pnl: Number(row.net_pnl ?? 0) }));
    }
    const values = new Map<string, number>();
    trades.forEach((trade) => {
      const day = String(trade.timestamp).slice(0, 10);
      values.set(day, (values.get(day) ?? 0) + Number(trade.net_pnl));
    });
    return [...values].map(([timestamp, daily_pnl]) => ({ timestamp: `${timestamp}T00:00:00Z`, daily_pnl }));
  }, [dailyReport, trades]);

  const cards = [
    ["Initial Equity", account.initial_equity],
    ["Current Equity", account.equity],
    ["Today’s P&L", account.daily_pnl],
    ["Total Net P&L", metrics.net_pnl],
    ["Return %", metrics.total_return_percent],
    ["Win Rate %", metrics.win_rate],
    ["Profit Factor", metrics.profit_factor ?? "—"],
    ["Expectancy", metrics.expectancy],
    ["Max Drawdown", metrics.maximum_drawdown],
    ["Open Positions", metrics.open_positions],
    ["Total Trades", metrics.trades],
  ];

  return (
    <main className="mx-auto max-w-[1600px] p-4 sm:p-8 space-y-7">
      {/* Header Banner - CRED Velvet Matte Obsidian */}
      <header className="cred-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.9)]">
        {/* Subtle Ambient Radial Glows */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-[#FFB800]/10 blur-3xl"></div>
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-[#00F5A0]/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#FFB800]/10 px-3 py-1 text-[11px] font-black tracking-wider uppercase text-[#FFB800] border border-[#FFB800]/30 shadow-[0_0_15px_rgba(255,184,0,0.2)]">
                <span>🧪</span> Paper Trading Lab
              </span>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                Production Logic · Zero Financial Risk
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Live-Market Simulation Sandbox
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              Public CoinDCX live data stream · production multi-factor strategy & risk engine · simulated order execution only.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div className="rounded-2xl border border-[#FFB800]/30 bg-[#FFB800]/10 px-4 py-2.5 text-center shadow-lg">
              <p className="text-xs font-black tracking-wider text-[#FFB800] uppercase">Simulated Execution</p>
              <p className="text-[10px] uppercase text-slate-400 font-mono mt-0.5">{status.engine_status ?? "Syncing..."}</p>
            </div>
          </div>
        </div>

        {/* Controls bar */}
        <div className="relative z-10 mt-6 pt-5 border-t border-white/[0.07] flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => action("start")}
              className="cred-btn-primary rounded-xl px-4 sm:px-5 py-2.5 text-xs font-black active:scale-95 transition"
            >
              Start Session
            </button>
            <button
              onClick={() => action("stop")}
              className="cred-btn-secondary rounded-xl px-3.5 sm:px-4 py-2.5 text-xs font-bold active:scale-95 transition"
            >
              Stop
            </button>
            <button
              onClick={() => action("clear-losses")}
              className="rounded-xl border border-[#00F5A0]/40 bg-[#00F5A0]/10 hover:bg-[#00F5A0]/20 text-[#00F5A0] px-3.5 py-2.5 text-xs font-bold transition flex items-center gap-1.5 active:scale-95"
              title="Clear consecutive loss lockout and resume paper trading"
            >
              <span>⚡</span> Unblock / Clear
            </button>
            {!resetArmed ? (
              <button
                onClick={() => setResetArmed(true)}
                className="rounded-xl border border-rose-500/30 bg-rose-950/20 hover:bg-rose-950/40 text-rose-300 px-3.5 py-2.5 text-xs font-bold transition active:scale-95"
              >
                Reset Account
              </button>
            ) : (
              <div className="flex flex-wrap items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-950/30 p-1.5 text-xs">
                <span className="text-slate-300 font-mono px-2 text-[11px]">
                  ${money(account.equity)} · {positions.length} open
                </span>
                <button
                  onClick={() => action("reset?confirmation=RESET%20PAPER%20TRADING")}
                  className="rounded-lg bg-rose-500 hover:bg-rose-400 px-3 py-1 font-bold text-black transition"
                >
                  Confirm
                </button>
                <button
                  onClick={() => setResetArmed(false)}
                  className="text-slate-400 hover:text-white px-2"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>

          {message && (
            <p className="text-xs font-mono text-[#00D9F5] bg-white/[0.04] border border-white/[0.06] rounded-xl px-3 py-1.5 w-full sm:w-auto text-center sm:text-left">
              {message}
            </p>
          )}
        </div>
      </header>

      {(status.trading_blocked || health.trading_blocked) && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-950/30 p-4 text-xs font-bold text-rose-300 shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span>⚠️</span>
            <span>PAPER TRADING BLOCKED: {status.block_reason || health.block_reason || "Risk circuit active"}</span>
          </div>
          <button
            onClick={() => action("clear-losses")}
            className="rounded-xl bg-[#00F5A0] hover:bg-[#00D9F5] text-slate-950 px-4 py-2 font-black text-xs transition active:scale-95 shrink-0 shadow-lg text-center"
          >
            Clear Circuit &amp; Unblock
          </button>
        </div>
      )}

      {/* Primary KPI Section */}
      {/* Mobile-First Hero Financial Card (<640px) */}
      <div className="sm:hidden cred-surface rounded-2xl p-5 border border-white/[0.08] shadow-2xl space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Current Equity</p>
            <p className="mt-1 text-3xl font-black text-white font-mono tracking-tight">
              ${money(account.equity)}
            </p>
          </div>
          <div className="text-right">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Today P&amp;L</p>
            <p className={`mt-1 text-xl font-black font-mono ${Number(account.daily_pnl ?? 0) >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
              {Number(account.daily_pnl ?? 0) >= 0 ? "+" : ""}${money(account.daily_pnl)}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 pt-3 border-t border-white/[0.06] text-xs">
          <div className="bg-white/[0.02] p-2.5 rounded-xl border border-white/[0.04]">
            <span className="text-slate-500 text-[10px] uppercase font-bold">Total Net PnL</span>
            <p className={`font-mono font-black text-sm mt-0.5 ${Number(metrics.net_pnl ?? 0) >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
              {Number(metrics.net_pnl ?? 0) >= 0 ? "+" : ""}${money(metrics.net_pnl)}
            </p>
          </div>
          <div className="bg-white/[0.02] p-2.5 rounded-xl border border-white/[0.04]">
            <span className="text-slate-500 text-[10px] uppercase font-bold">Win Rate</span>
            <p className="font-mono font-black text-sm text-white mt-0.5">
              {metrics.win_rate != null ? `${money(metrics.win_rate)}%` : "—"}
            </p>
          </div>
          <div className="bg-white/[0.02] p-2.5 rounded-xl border border-white/[0.04]">
            <span className="text-slate-500 text-[10px] uppercase font-bold">Open Positions</span>
            <p className="font-mono font-black text-sm text-[#00D9F5] mt-0.5">
              {positions.length} Active
            </p>
          </div>
          <div className="bg-white/[0.02] p-2.5 rounded-xl border border-white/[0.04]">
            <span className="text-slate-500 text-[10px] uppercase font-bold">Max Drawdown</span>
            <p className="font-mono font-black text-sm text-rose-400 mt-0.5">
              ${money(account.drawdown ?? metrics.maximum_drawdown)}
            </p>
          </div>
        </div>

        {/* Expandable toggle for remaining metrics */}
        <button
          onClick={() => setShowAllKpis(!showAllKpis)}
          className="w-full text-center text-[11px] font-bold text-slate-400 hover:text-white py-1.5 transition active:scale-95"
        >
          {showAllKpis ? "▲ Hide Secondary Metrics" : "▼ Show All 11 Performance Metrics"}
        </button>

        {showAllKpis && (
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/[0.06]">
            {cards.slice(4).map(([label, value]) => (
              <div key={String(label)} className="bg-white/[0.02] p-2 rounded-xl border border-white/[0.04]">
                <p className="text-[9px] uppercase font-bold text-slate-500 truncate">{label}</p>
                <p className="text-xs font-mono font-bold text-slate-200 mt-0.5">
                  {typeof value === "number" ? money(value) : String(value ?? "—")}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Desktop/Tablet Grid (>=640px) */}
      <section className="hidden sm:grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-6">
        {cards.map(([label, value]) => (
          <Card key={String(label)} className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
            <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{label}</p>
            <p className="mt-2 text-xl font-black text-white font-mono tracking-tight">
              {typeof value === "number" ? money(value) : String(value ?? "—")}
            </p>
          </Card>
        ))}
      </section>

      {/* Stream Feed Telemetry Cards */}
      <section className="grid grid-cols-3 gap-2 sm:gap-4">
        <Card className="p-3 sm:p-5 rounded-xl sm:rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl text-center sm:text-left">
          <p className="text-[9px] sm:text-[10px] font-black uppercase tracking-wider text-slate-500 truncate">Opportunities</p>
          <p className="mt-1 sm:mt-2 text-xl sm:text-3xl font-black text-[#FFB800] font-mono">{status.live_feed?.current_opportunities ?? 0}</p>
        </Card>
        <Card className="p-3 sm:p-5 rounded-xl sm:rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl text-center sm:text-left">
          <p className="text-[9px] sm:text-[10px] font-black uppercase tracking-wider text-slate-500 truncate">Setups</p>
          <p className="mt-1 sm:mt-2 text-xl sm:text-3xl font-black text-[#00F5A0] font-mono">{status.live_feed?.current_setups ?? 0}</p>
        </Card>
        <Card className="p-3 sm:p-5 rounded-xl sm:rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl text-center sm:text-left">
          <p className="text-[9px] sm:text-[10px] font-black uppercase tracking-wider text-slate-500 truncate">Decisions</p>
          <p className="mt-1 sm:mt-2 text-xl sm:text-3xl font-black text-[#00D9F5] font-mono">{status.live_feed?.risk_decisions ?? 0}</p>
        </Card>
      </section>

      {/* Equity & P&L Charts */}
      <section className="grid gap-5 lg:grid-cols-2">
        <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
          <h2 className="text-base font-black text-white tracking-tight mb-4">Simulated Equity Curve</h2>
          <PaperChart points={curve} field="equity" />
        </Card>
        <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
          <h2 className="text-base font-black text-white tracking-tight mb-4">Drawdown Profile</h2>
          <PaperChart points={curve} field="drawdown" color="#FF3366" />
        </Card>
        <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
          <h2 className="text-base font-black text-white tracking-tight mb-4">Cumulative P&L</h2>
          <PaperChart points={curve} field="cumulative_pnl" color="#00D9F5" />
        </Card>
        <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
          <h2 className="text-base font-black text-white tracking-tight mb-4">Daily P&L</h2>
          {daily.length ? (
            <PaperChart points={daily} field="daily_pnl" color="#00F5A0" />
          ) : (
            <p className="mt-8 text-sm text-slate-500 text-center py-12">No completed paper trades yet.</p>
          )}
        </Card>
      </section>

      {/* Active Simulated Positions */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-black text-white tracking-tight">Active Simulated Positions</h2>
          <span className="text-xs text-slate-500 font-mono">{positions.length} Active</span>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          {positions.length ? (
            positions.map((p) => (
              <Card key={p.position_id} className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-black text-lg text-white">
                      {p.symbol} · <span className={String(p.direction).toUpperCase() === "LONG" ? "text-[#00F5A0]" : "text-[#FF3366]"}>{String(p.direction).toUpperCase()}</span>
                    </p>
                    <p className="text-xs text-slate-400 capitalize mt-0.5">
                      {p.strategy} · Opp {p.opportunity_score} · Setup {p.setup_score}
                    </p>
                  </div>
                  <button
                    onClick={() => action(`close/${p.position_id}`)}
                    className="cred-btn-secondary px-3 py-1 rounded-lg text-xs font-bold text-[#FFB800]"
                  >
                    Simulate Close
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-3 rounded-xl bg-[#060608] p-3.5 border border-white/[0.05] text-xs font-mono">
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Entry</span>
                    <p className="text-white font-black mt-0.5">${money(p.entry_price)}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Current</span>
                    <p className="text-white font-black mt-0.5">${money(p.current_price)}</p>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Unrealized</span>
                    <p className={`font-black mt-0.5 ${Number(p.unrealized_pnl) >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                      ${money(p.unrealized_pnl)}
                    </p>
                  </div>
                  <div className="pt-2 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Stop</span>
                    <p className="text-[#FF3366] font-bold mt-0.5">${money(p.stop_price)}</p>
                  </div>
                  <div className="pt-2 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Target</span>
                    <p className="text-[#00F5A0] font-bold mt-0.5">${money(p.target_price)}</p>
                  </div>
                  <div className="pt-2 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Current R</span>
                    <p className="text-[#00D9F5] font-bold mt-0.5">{money(p.current_r)}</p>
                  </div>
                  <div className="pt-2 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Quantity</span>
                    <p className="text-slate-300 mt-0.5">{money(p.quantity)}</p>
                  </div>
                  <div className="pt-2 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Notional</span>
                    <p className="text-slate-300 mt-0.5">${money(p.notional)}</p>
                  </div>
                  <div className="pt-2 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold">Duration</span>
                    <p className="text-slate-300 mt-0.5">{money(p.duration_minutes)}m</p>
                  </div>
                </div>
              </Card>
            ))
          ) : (
            <Card className="p-8 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] text-center text-slate-500 text-sm">
              No open simulated positions.
            </Card>
          )}
        </div>
      </section>

      {/* Trade Log */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base sm:text-lg font-black text-white tracking-tight">Simulated Execution Log</h2>
          <span className="text-xs text-slate-500 font-mono">{trades.length} Completed</span>
        </div>

        {/* Mobile View: High-Density Tactile Cards */}
        <div className="md:hidden space-y-3">
          {trades.map((t) => {
            const net = Number(t.net_pnl);
            const isLong = String(t.direction).toUpperCase() === "LONG";
            return (
              <div
                key={t.trade_id}
                className="cred-surface rounded-2xl p-4 border border-white/[0.07] space-y-2.5 shadow-lg"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white text-sm">{t.symbol}</span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase ${
                      isLong
                        ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30"
                        : "bg-[#FF3366]/15 text-[#FF3366] border border-[#FF3366]/30"
                    }`}>
                      {String(t.direction).toUpperCase()}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className={`font-mono font-black text-base ${net >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                      {net >= 0 ? "+" : ""}${money(net)}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono pt-2 border-t border-white/[0.04]">
                  <span>{new Date(t.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} · {t.exit_reason || "exit"}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[#00D9F5] font-bold">{money(t.r_multiple)}R</span>
                    <span className="text-slate-500">fee ${money(t.fees)}</span>
                  </div>
                </div>
              </div>
            );
          })}
          {!trades.length && (
            <Card className="p-8 text-center text-sm text-slate-500 rounded-2xl border border-white/[0.07]">
              No paper activity recorded yet.
            </Card>
          )}
        </div>

        {/* Desktop View: Full Table */}
        <Card className="hidden md:block p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead>
                <tr className="border-b border-white/[0.07] text-[10px] font-black uppercase tracking-[0.15em] text-slate-500">
                  <th className="pb-3 px-3">Time</th>
                  <th className="pb-3 px-3">Symbol</th>
                  <th className="pb-3 px-3">Strategy</th>
                  <th className="pb-3 px-3">Direction</th>
                  <th className="pb-3 px-3">Exit Reason</th>
                  <th className="pb-3 px-3 text-right">Net P&amp;L</th>
                  <th className="pb-3 px-3 text-right">R Multiple</th>
                  <th className="pb-3 px-3 text-right">Fees</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {trades.map((t) => {
                  const net = Number(t.net_pnl);
                  return (
                    <tr key={t.trade_id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 px-3 font-mono text-slate-400">{new Date(t.timestamp).toLocaleString()}</td>
                      <td className="py-3 px-3 font-bold text-white">{t.symbol}</td>
                      <td className="py-3 px-3 text-slate-300 capitalize">{t.strategy}</td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider ${
                          String(t.direction).toUpperCase() === "LONG"
                            ? "bg-[#00F5A0]/10 text-[#00F5A0] border border-[#00F5A0]/30"
                            : "bg-[#FF3366]/10 text-[#FF3366] border border-[#FF3366]/30"
                        }`}>
                          {String(t.direction).toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400">{t.exit_reason}</td>
                      <td className={`py-3 px-3 text-right font-mono font-black ${net >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                        {net >= 0 ? "+" : ""}${money(net)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#00D9F5]">{money(t.r_multiple)}R</td>
                      <td className="py-3 px-3 text-right font-mono text-slate-400">${money(t.fees)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!trades.length && (
              <p className="py-8 text-center text-sm text-slate-500">No paper activity recorded yet.</p>
            )}
          </div>
        </Card>
      </section>

      <section className="grid gap-5 xl:grid-cols-2">
        <Card className="p-4 sm:p-6 rounded-2xl sm:rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl overflow-hidden">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-base sm:text-lg font-black text-white tracking-tight">Daily Paper P&amp;L</h2>
              <p className="mt-0.5 text-xs text-slate-500">UTC trading day · journal-derived closed-trade totals</p>
            </div>
            <span className="text-xs text-slate-500 font-mono">{dailyReport.length} days</span>
          </div>

          {/* Mobile View: High-Density Day Chips */}
          <div className="md:hidden space-y-2.5">
            {dailyReport.map((row) => {
              const pnl = Number(row.net_pnl ?? 0);
              return (
                <div key={row.date} className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] flex items-center justify-between">
                  <div>
                    <span className="font-mono text-white text-xs font-bold">{row.date}{row.is_current_utc_day ? " · today" : ""}</span>
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                      {row.trade_count} trades · {row.wins}W / {row.losses}L · fee ${money(row.fees)}
                    </p>
                  </div>
                  <span className={`font-mono font-black text-sm ${pnl >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                    {pnl >= 0 ? "+" : ""}${money(pnl)}
                  </span>
                </div>
              );
            })}
            {!dailyReport.length && (
              <p className="py-6 text-center text-xs text-slate-500">No daily records yet.</p>
            )}
          </div>

          {/* Desktop View: Full Table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-xs">
              <thead><tr className="border-b border-white/[0.07] text-[10px] font-black uppercase tracking-[0.15em] text-slate-500"><th className="pb-3 px-2">Day</th><th className="pb-3 px-2 text-right">Trades</th><th className="pb-3 px-2 text-right">W / L</th><th className="pb-3 px-2 text-right">Fees</th><th className="pb-3 px-2 text-right">Net P&amp;L</th></tr></thead>
              <tbody className="divide-y divide-white/[0.04]">{dailyReport.map((row) => { const pnl = Number(row.net_pnl ?? 0); return <tr key={row.date}><td className="py-3 px-2 font-mono text-slate-300">{row.date}{row.is_current_utc_day ? " · today" : ""}</td><td className="py-3 px-2 text-right font-mono text-white">{row.trade_count}</td><td className="py-3 px-2 text-right font-mono text-slate-300">{row.wins} / {row.losses}</td><td className="py-3 px-2 text-right font-mono text-slate-400">${money(row.fees)}</td><td className={`py-3 px-2 text-right font-mono font-black ${pnl >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>{pnl >= 0 ? "+" : ""}${money(pnl)}</td></tr>; })}</tbody>
            </table>
          </div>
        </Card>

        <Card className="p-4 sm:p-6 rounded-2xl sm:rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl overflow-hidden">
          <div className="flex items-center justify-between gap-3 mb-4">
            <div><h2 className="text-base sm:text-lg font-black text-white tracking-tight">Paper Orders &amp; Protection</h2><p className="mt-0.5 text-xs text-slate-500">Entry fills plus simulated stop-loss and take-profit orders</p></div>
            <span className="text-xs text-slate-500 font-mono">{orders.length} orders</span>
          </div>

          {/* Mobile View: High-Density Order Chips */}
          <div className="md:hidden space-y-2.5 max-h-[330px] overflow-y-auto">
            {orders.map((order) => (
              <div key={order.order_id} className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.05] flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white text-xs">{order.symbol}</span>
                    <span className="text-[10px] text-slate-400 capitalize font-mono">({String(order.order_type).replaceAll("_", " ")})</span>
                  </div>
                  <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                    Qty {money(order.quantity)} · ${money(order.executed_price ?? order.requested_price)}
                  </p>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold text-[#00D9F5] bg-[#00D9F5]/10 border border-[#00D9F5]/20">
                  {order.status}
                </span>
              </div>
            ))}
            {!orders.length && (
              <p className="py-6 text-center text-xs text-slate-500">No paper orders yet.</p>
            )}
          </div>

          {/* Desktop View: Full Table */}
          <div className="hidden md:block max-h-[330px] overflow-auto rounded-xl border border-white/[0.05]">
            <table className="w-full min-w-[620px] text-left text-xs"><thead className="sticky top-0 bg-[#0e0e12]"><tr className="border-b border-white/[0.07] text-[10px] font-black uppercase tracking-[0.15em] text-slate-500"><th className="p-3">Symbol</th><th className="p-3">Type</th><th className="p-3">Status</th><th className="p-3 text-right">Price</th><th className="p-3 text-right">Qty</th><th className="p-3 text-right">Fees</th></tr></thead><tbody className="divide-y divide-white/[0.04]">{orders.map((order) => <tr key={order.order_id}><td className="p-3 font-bold text-white">{order.symbol}</td><td className="p-3 capitalize text-slate-300">{String(order.order_type).replaceAll("_", " ")}</td><td className="p-3 uppercase text-[#00D9F5]">{order.status}</td><td className="p-3 text-right font-mono text-slate-300">${money(order.executed_price ?? order.requested_price)}</td><td className="p-3 text-right font-mono text-slate-300">{money(order.quantity)}</td><td className="p-3 text-right font-mono text-slate-400">${money(order.fees)}</td></tr>)}</tbody></table>
            {!orders.length && <p className="py-8 text-center text-sm text-slate-500">No paper orders yet. Approved strategy setups will appear here.</p>}
          </div>
        </Card>
      </section>
    </main>
  );
}
