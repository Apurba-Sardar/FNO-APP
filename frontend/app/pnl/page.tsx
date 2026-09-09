"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AuthGuard } from "@/components/auth-guard";
import { getApiUrl } from "@/lib/api";
import { formatIST, formatISTTime } from "@/lib/format";

interface TradeItem {
  position_id: string;
  exchange_position_id?: string;
  pair: string;
  direction: string;
  quantity: number;
  entry_price: number;
  exit_price: number;
  realized_pnl: number;
  roe_pct: number;
  margin: number;
  leverage: number;
  exit_reason: string;
  bot_managed: boolean;
  created_at: string | null;
  closed_at: string | null;
  duration_seconds: number;
  is_win: boolean;
}

interface DailySummary {
  date: string;
  realized_pnl: number;
  profit: number;
  loss: number;
  wins: number;
  losses: number;
  trades_count: number;
  win_rate_pct: number;
  trades: TradeItem[];
}

interface WeeklySummary {
  week_id: string;
  week_label: string;
  realized_pnl: number;
  profit: number;
  loss: number;
  wins: number;
  losses: number;
  trades_count: number;
  win_rate_pct: number;
}

interface PnlSummary {
  total_realized_pnl: number;
  total_trades: number;
  total_wins: number;
  total_losses: number;
  win_rate_pct: number;
  profit_factor: number;
  today_pnl: number;
  today_wins: number;
  today_losses: number;
  today_profit: number;
  today_loss: number;
  daily_target_cap: number;
  daily_target_progress_pct: number;
  this_week_pnl: number;
  this_week_wins: number;
  this_week_losses: number;
}

export default function PnlLogsPage() {
  const [activeTab, setActiveTab] = useState<"daily" | "weekly" | "all">("daily");
  const [filterType, setFilterType] = useState<"all" | "wins" | "losses">("all");
  const [searchSymbol, setSearchSymbol] = useState("");
  const [summary, setSummary] = useState<PnlSummary | null>(null);
  const [dailyBreakdown, setDailyBreakdown] = useState<DailySummary[]>([]);
  const [weeklyBreakdown, setWeeklyBreakdown] = useState<WeeklySummary[]>([]);
  const [trades, setTrades] = useState<TradeItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [expandedDays, setExpandedDays] = useState<Record<string, boolean>>({});

  const headers = useCallback(() => {
    const head: Record<string, string> = { "Content-Type": "application/json" };
    const token = typeof window !== "undefined" ? localStorage.getItem("live_operator_token") || "LIVE_OPERATOR_TOKEN_2026" : "LIVE_OPERATOR_TOKEN_2026";
    head["x-live-operator-token"] = token;
    return head;
  }, []);

  const loadData = useCallback(async () => {
    try {
      const apiBase = getApiUrl();
      const res = await fetch(`${apiBase}/live/pnl-logs?limit=300`, { headers: headers() });
      if (!res.ok) throw new Error("Failed to load PnL logs");
      const data = await res.json();
      setSummary(data.summary || null);
      setDailyBreakdown(data.daily_breakdown || []);
      setWeeklyBreakdown(data.weekly_breakdown || []);
      setTrades(data.trades || []);
      setLastRefreshed(new Date());

      // Auto-expand today
      if (data.daily_breakdown?.length > 0) {
        setExpandedDays((prev) => ({
          ...prev,
          [data.daily_breakdown[0].date]: true,
        }));
      }
    } catch (err) {
      console.error("Failed to load PnL history", err);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const toggleDay = (dateStr: string) => {
    setExpandedDays((prev) => ({ ...prev, [dateStr]: !prev[dateStr] }));
  };

  const filteredTrades = useMemo(() => {
    return trades.filter((t) => {
      if (searchSymbol && !t.pair.toLowerCase().includes(searchSymbol.toLowerCase())) {
        return false;
      }
      if (filterType === "wins") return t.is_win;
      if (filterType === "losses") return !t.is_win;
      return true;
    });
  }, [trades, searchSymbol, filterType]);

  const formatUsdt = (val: number | undefined | null) => {
    if (val === undefined || val === null) return "$0.00";
    const sign = val > 0 ? "+" : val < 0 ? "-" : "";
    return `${sign}$${Math.abs(val).toFixed(2)}`;
  };

  const formatDuration = (sec: number) => {
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}m ${s}s`;
  };

  return (
    <AuthGuard>
      <div className="min-h-screen bg-[#050507] text-[#EDEDED] p-4 md:p-8 space-y-6">
        {/* Page Top Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/[0.07] pb-6">
          <div>
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-[#00F5A0] via-teal-400 to-[#00D9F5] flex items-center justify-center font-black text-black text-xl shadow-[0_0_25px_rgba(0,245,160,0.35),inset_0_1px_0_rgba(255,255,255,0.8)]">
                📊
              </div>
              <div>
                <h1 className="text-2xl font-black tracking-tight text-white flex items-center gap-2">
                  PnL & Trade Performance Ledger
                  <span className="px-2.5 py-0.5 rounded-full text-[10px] uppercase tracking-widest font-mono font-bold bg-[#00F5A0]/10 text-[#00F5A0] border border-[#00F5A0]/30 shadow-[0_0_15px_rgba(0,245,160,0.15)]">
                    Audit Verified
                  </span>
                </h1>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Institutional record of all algorithmic scalps, net realized cash settlements, daily compounding targets, and weekly performance.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <Link
              href="/live"
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-[#FF3366] to-[#E11D48] text-white text-xs font-bold shadow-[0_0_25px_rgba(255,51,102,0.4)] hover:scale-105 transition"
            >
              <span className="h-2 w-2 rounded-full bg-white animate-pulse" />
              Live Dashboard
            </Link>

            <button
              onClick={loadData}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#0c0c10] border border-white/[0.08] hover:bg-white/[0.06] hover:border-white/[0.14] text-xs font-semibold text-zinc-300 transition shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
            >
              <svg className={`w-3.5 h-3.5 ${loading ? "animate-spin text-[#00F5A0]" : "text-zinc-400"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>{loading ? "Syncing..." : "Refresh"}</span>
            </button>
          </div>
        </div>

        {/* Top 4 Performance KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* KPI 1: Today's Net PnL */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-[#111115] to-[#08080b] border border-[#00F5A0]/25 p-5 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.95),0_0_30px_rgba(0,245,160,0.06),inset_0_1px_0_0_rgba(0,245,160,0.3)] transition-all hover:border-[#00F5A0]/40">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 font-mono">
              <span>Today&apos;s Realized Net</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#00F5A0]/10 text-[#00F5A0] border border-[#00F5A0]/30">
                {summary?.today_wins ?? 0}W - {summary?.today_losses ?? 0}L
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <b className={`text-3xl font-black font-mono tracking-tight ${
                (summary?.today_pnl ?? 0) >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"
              }`}>
                {formatUsdt(summary?.today_pnl)}
              </b>
              <span className="text-xs font-semibold text-zinc-500">USDT</span>
            </div>

            {/* Target progress bar */}
            <div className="mt-4 pt-3 border-t border-white/[0.06]">
              <div className="flex items-center justify-between text-[10px] text-zinc-400 mb-1.5 font-mono">
                <span>Daily Target ($20 Cap)</span>
                <span className="font-bold text-white">{summary?.daily_target_progress_pct ?? 0}%</span>
              </div>
              <div className="h-1.5 w-full bg-[#16161c] rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[#00F5A0] to-[#00D9F5] rounded-full transition-all duration-500 shadow-[0_0_10px_rgba(0,245,160,0.5)]"
                  style={{ width: `${Math.min(100, summary?.daily_target_progress_pct ?? 0)}%` }}
                />
              </div>
            </div>
          </div>

          {/* KPI 2: This Week's Net PnL */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-[#111115] to-[#08080b] border border-[#00D9F5]/25 p-5 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.95),0_0_30px_rgba(0,217,245,0.06),inset_0_1px_0_0_rgba(0,217,245,0.3)] transition-all hover:border-[#00D9F5]/40">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 font-mono">
              <span>This Week&apos;s Net P&L</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#00D9F5]/10 text-[#00D9F5] border border-[#00D9F5]/30">
                {summary?.this_week_wins ?? 0}W - {summary?.this_week_losses ?? 0}L
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <b className={`text-3xl font-black font-mono tracking-tight ${
                (summary?.this_week_pnl ?? 0) >= 0 ? "text-[#00D9F5]" : "text-[#FF3366]"
              }`}>
                {formatUsdt(summary?.this_week_pnl)}
              </b>
              <span className="text-xs font-semibold text-zinc-500">USDT</span>
            </div>

            <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-400">
              <span>Weekly Compounding</span>
              <span className="font-mono text-[#00D9F5] font-bold">Active 7-Day</span>
            </div>
          </div>

          {/* KPI 3: All-Time Net Realized PnL */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-[#111115] to-[#08080b] border border-white/[0.08] p-5 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.95),inset_0_1px_0_0_rgba(255,255,255,0.07)] transition-all hover:border-white/[0.14]">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 font-mono">
              <span>Total Realized P&L</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-purple-500/10 text-purple-300 border border-purple-500/30">
                {summary?.total_trades ?? 0} Trades
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <b className={`text-3xl font-black font-mono tracking-tight ${
                (summary?.total_realized_pnl ?? 0) >= 0 ? "text-purple-300" : "text-[#FF3366]"
              }`}>
                {formatUsdt(summary?.total_realized_pnl)}
              </b>
              <span className="text-xs font-semibold text-zinc-500">USDT</span>
            </div>

            <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-400">
              <span>Win Rate</span>
              <span className="font-mono text-[#00F5A0] font-bold">{summary?.win_rate_pct ?? 0}%</span>
            </div>
          </div>

          {/* KPI 4: Profit Factor & Risk Shield */}
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-b from-[#111115] to-[#08080b] border border-[#FFB800]/25 p-5 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.95),0_0_30px_rgba(255,184,0,0.06),inset_0_1px_0_0_rgba(255,184,0,0.3)] transition-all hover:border-[#FFB800]/40">
            <div className="flex items-center justify-between text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 font-mono">
              <span>Profit Factor</span>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-[#FFB800]/10 text-[#FFB800] border border-[#FFB800]/30">
                Shield Active
              </span>
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <b className="text-3xl font-black font-mono tracking-tight text-[#FFB800]">
                {summary?.profit_factor ?? 1.0}x
              </b>
              <span className="text-xs font-semibold text-zinc-500">Ratio</span>
            </div>

            <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-400">
              <span>Max Daily Loss Cap</span>
              <span className="font-mono text-[#FF3366] font-bold">-$3.50 USDT</span>
            </div>
          </div>
        </div>

        {/* View Selection Tabs */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0c0c10]/95 p-2 rounded-2xl border border-white/[0.07] shadow-[0_12px_30px_rgba(0,0,0,0.85)]">
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setActiveTab("daily")}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                activeTab === "daily"
                  ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/35 shadow-[0_0_15px_rgba(0,245,160,0.2)]"
                  : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <span>📅</span>
              <span>Daily Breakdown</span>
              <span className="px-1.5 py-0.2 rounded-full bg-black/50 text-[10px] font-mono border border-white/[0.06]">
                {dailyBreakdown.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab("weekly")}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                activeTab === "weekly"
                  ? "bg-[#00D9F5]/15 text-[#00D9F5] border border-[#00D9F5]/35 shadow-[0_0_15px_rgba(0,217,245,0.2)]"
                  : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <span>📊</span>
              <span>Weekly Performance</span>
              <span className="px-1.5 py-0.2 rounded-full bg-black/50 text-[10px] font-mono border border-white/[0.06]">
                {weeklyBreakdown.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab("all")}
              className={`px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 ${
                activeTab === "all"
                  ? "bg-purple-500/15 text-purple-300 border border-purple-500/35 shadow-[0_0_15px_rgba(168,85,247,0.2)]"
                  : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
              }`}
            >
              <span>📋</span>
              <span>All Trades Log</span>
              <span className="px-1.5 py-0.2 rounded-full bg-black/50 text-[10px] font-mono border border-white/[0.06]">
                {trades.length}
              </span>
            </button>
          </div>

          {/* Search & Win/Loss Filter for Trades tab */}
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="Search pair (e.g. XRP)..."
              value={searchSymbol}
              onChange={(e) => setSearchSymbol(e.target.value)}
              className="bg-[#08080a] border border-white/[0.08] rounded-xl px-3 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-[#00F5A0]/60 w-36 sm:w-44"
            />
            <div className="flex items-center rounded-xl bg-[#08080a] p-1 border border-white/[0.08] text-xs">
              <button
                onClick={() => setFilterType("all")}
                className={`px-2.5 py-1 rounded-lg font-semibold transition ${
                  filterType === "all" ? "bg-white/[0.12] text-white shadow-sm" : "text-zinc-400 hover:text-white"
                }`}
              >
                All
              </button>
              <button
                onClick={() => setFilterType("wins")}
                className={`px-2.5 py-1 rounded-lg font-semibold transition ${
                  filterType === "wins" ? "bg-[#00F5A0]/20 text-[#00F5A0]" : "text-zinc-400 hover:text-[#00F5A0]"
                }`}
              >
                Wins
              </button>
              <button
                onClick={() => setFilterType("losses")}
                className={`px-2.5 py-1 rounded-lg font-semibold transition ${
                  filterType === "losses" ? "bg-[#FF3366]/20 text-rose-300" : "text-zinc-400 hover:text-rose-400"
                }`}
              >
                Losses
              </button>
            </div>
          </div>
        </div>

        {/* ── TAB 1: DAILY BREAKDOWN ── */}
        {activeTab === "daily" && (
          <div className="space-y-4">
            {dailyBreakdown.length === 0 ? (
              <div className="rounded-2xl border border-white/[0.07] bg-[#0c0c10]/95 p-12 text-center text-zinc-400 text-sm shadow-[0_16px_40px_-15px_rgba(0,0,0,0.9)]">
                No closed scalp trades recorded yet today. When the bot punches and exits positions, each trade will be logged here automatically.
              </div>
            ) : (
              dailyBreakdown.map((day) => {
                const isExpanded = !!expandedDays[day.date];
                const isToday = day.date === new Date().toISOString().slice(0, 10);

                return (
                  <div
                    key={day.date}
                    className="rounded-2xl border border-white/[0.07] bg-[#0c0c10]/95 overflow-hidden transition shadow-[0_16px_40px_-15px_rgba(0,0,0,0.9)] hover:border-white/[0.13]"
                  >
                    {/* Day Summary Bar */}
                    <div
                      onClick={() => toggleDay(day.date)}
                      className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 cursor-pointer hover:bg-white/[0.02] transition"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`h-9 w-9 rounded-xl flex items-center justify-center font-bold text-sm ${
                          day.realized_pnl >= 0 ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30" : "bg-[#FF3366]/15 text-rose-400 border border-[#FF3366]/30"
                        }`}>
                          {day.realized_pnl >= 0 ? "↗" : "↘"}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-white text-sm">
                              {day.date}
                            </h3>
                            {isToday && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-[#00F5A0]/20 text-[#00F5A0] border border-[#00F5A0]/40 font-mono">
                                Today
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-zinc-400 mt-0.5">
                            {day.trades_count} Trades punched • {day.wins} Wins / {day.losses} Losses
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-5 self-end sm:self-auto">
                        <div className="text-right">
                          <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-[0.14em] font-mono">Win Rate</span>
                          <span className="text-xs font-mono font-bold text-[#00F5A0]">{day.win_rate_pct}%</span>
                        </div>

                        <div className="text-right border-l border-white/[0.08] pl-5">
                          <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-[0.14em] font-mono">Net Realized</span>
                          <b className={`text-base font-mono font-black ${
                            day.realized_pnl >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"
                          }`}>
                            {formatUsdt(day.realized_pnl)} <span className="text-[10px] font-normal text-zinc-500">USDT</span>
                          </b>
                        </div>

                        <div className="text-zinc-500 text-sm">
                          {isExpanded ? "▲" : "▼"}
                        </div>
                      </div>
                    </div>

                    {/* Collapsible Day's Trades Table */}
                    {isExpanded && (
                      <div className="border-t border-white/[0.07] bg-[#08080b]/90 p-4 overflow-x-auto">
                        {day.trades.length === 0 ? (
                          <p className="text-xs text-zinc-400 p-4 text-center">No trades closed on this day yet.</p>
                        ) : (
                          <table className="w-full text-left text-xs border-collapse">
                            <thead>
                              <tr className="border-b border-white/[0.07] text-[10px] uppercase tracking-[0.14em] text-zinc-400 font-mono font-bold">
                                <th className="pb-2.5">Pair / Side</th>
                                <th className="pb-2.5">Entry Price</th>
                                <th className="pb-2.5">Exit Price</th>
                                <th className="pb-2.5">Duration</th>
                                <th className="pb-2.5">Exit Reason</th>
                                <th className="pb-2.5 text-right">ROE %</th>
                                <th className="pb-2.5 text-right">Net Profit</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/[0.03]">
                              {day.trades.map((t) => (
                                <tr key={t.position_id} className="hover:bg-white/[0.02]">
                                  <td className="py-3 font-bold">
                                    <span className="text-white font-mono">{t.pair}</span>
                                    <span className={`ml-2 px-2 py-0.5 rounded-full text-[9px] font-mono uppercase font-bold ${
                                      t.direction === "buy" || t.direction === "long" ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30" : "bg-purple-500/15 text-purple-300 border border-purple-500/30"
                                    }`}>
                                      {t.direction}
                                    </span>
                                  </td>
                                  <td className="py-3 font-mono text-zinc-300">${t.entry_price}</td>
                                  <td className="py-3 font-mono text-zinc-300">${t.exit_price}</td>
                                  <td className="py-3 font-mono text-zinc-400">{formatDuration(t.duration_seconds)}</td>
                                  <td className="py-3">
                                    <span className="text-[11px] text-zinc-300 font-mono">
                                      {t.exit_reason}
                                    </span>
                                  </td>
                                  <td className={`py-3 font-mono font-bold text-right ${t.roe_pct >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                                    {t.roe_pct >= 0 ? "+" : ""}{t.roe_pct}%
                                  </td>
                                  <td className={`py-3 font-mono font-bold text-right ${t.realized_pnl >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                                    {formatUsdt(t.realized_pnl)} USDT
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* ── TAB 2: WEEKLY PERFORMANCE ── */}
        {activeTab === "weekly" && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {weeklyBreakdown.length === 0 ? (
              <div className="col-span-full rounded-2xl border border-white/[0.07] bg-[#0c0c10]/95 p-12 text-center text-zinc-400 text-sm shadow-[0_16px_40px_-15px_rgba(0,0,0,0.9)]">
                No weekly summaries available yet.
              </div>
            ) : (
              weeklyBreakdown.map((week) => (
                <div
                  key={week.week_id}
                  className="rounded-2xl border border-white/[0.07] bg-gradient-to-b from-[#111115] to-[#08080b] p-5 shadow-[0_20px_45px_-15px_rgba(0,0,0,0.95),inset_0_1px_0_0_rgba(255,255,255,0.07)] hover:border-white/[0.14] transition-all flex flex-col justify-between space-y-4"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-bold text-white text-base">{week.week_label}</h4>
                      <p className="text-xs text-zinc-400 font-mono mt-0.5">{week.week_id}</p>
                    </div>
                    <span className={`px-2.5 py-1 rounded-xl text-xs font-mono font-bold ${
                      week.realized_pnl >= 0 ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30 shadow-[0_0_10px_rgba(0,245,160,0.15)]" : "bg-[#FF3366]/15 text-rose-300 border border-[#FF3366]/30 shadow-[0_0_10px_rgba(255,51,102,0.15)]"
                    }`}>
                      {formatUsdt(week.realized_pnl)} USDT
                    </span>
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-3 border-t border-white/[0.06] text-center">
                    <div className="bg-[#08080b] rounded-xl p-2.5 border border-white/[0.05]">
                      <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-wider font-mono">Trades</span>
                      <b className="text-sm font-mono text-white mt-0.5 block">{week.trades_count}</b>
                    </div>
                    <div className="bg-[#08080b] rounded-xl p-2.5 border border-white/[0.05]">
                      <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-wider font-mono">Win Rate</span>
                      <b className="text-sm font-mono text-[#00F5A0] mt-0.5 block">{week.win_rate_pct}%</b>
                    </div>
                    <div className="bg-[#08080b] rounded-xl p-2.5 border border-white/[0.05]">
                      <span className="text-[10px] uppercase font-bold text-zinc-400 block tracking-wider font-mono">Wins/Losses</span>
                      <b className="text-sm font-mono text-[#00D9F5] mt-0.5 block">{week.wins}W / {week.losses}L</b>
                    </div>
                  </div>

                  <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-xs text-zinc-400 font-mono">
                    <span>Gains: +${week.profit.toFixed(2)}</span>
                    <span>Losses: -${week.loss.toFixed(2)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* ── TAB 3: ALL TRADES LOG TABLE ── */}
        {activeTab === "all" && (
          <div className="rounded-2xl border border-white/[0.07] bg-[#0c0c10]/95 overflow-hidden shadow-[0_16px_40px_-15px_rgba(0,0,0,0.9)]">
            <div className="p-4 border-b border-white/[0.07] flex items-center justify-between">
              <h3 className="font-bold text-white text-sm">
                Closed Trades History ({filteredTrades.length} Trades)
              </h3>
              <span className="text-xs text-zinc-400 font-mono">
                Last synced: {lastRefreshed ? formatISTTime(lastRefreshed) : "—"}
              </span>
            </div>

            <div className="overflow-x-auto">
              {filteredTrades.length === 0 ? (
                <p className="p-12 text-center text-xs text-zinc-400">No matching trades found.</p>
              ) : (
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-[#08080a] border-b border-white/[0.07] text-[10px] uppercase tracking-[0.14em] text-zinc-400 font-bold font-mono">
                      <th className="py-3 px-4">Pair</th>
                      <th className="py-3 px-4">Side</th>
                      <th className="py-3 px-4">Size</th>
                      <th className="py-3 px-4">Entry Px</th>
                      <th className="py-3 px-4">Exit Px</th>
                      <th className="py-3 px-4">Duration</th>
                      <th className="py-3 px-4">Exit Reason</th>
                      <th className="py-3 px-4 text-right">ROE %</th>
                      <th className="py-3 px-4 text-right">Net P&L</th>
                      <th className="py-3 px-4 text-right">Closed (IST)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.03]">
                    {filteredTrades.map((t) => (
                      <tr key={t.position_id} className="hover:bg-white/[0.02]">
                        <td className="py-3 px-4 font-bold text-white font-mono">{t.pair}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-mono uppercase font-bold ${
                            t.direction === "buy" || t.direction === "long"
                              ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30"
                              : "bg-purple-500/15 text-purple-300 border border-purple-500/30"
                          }`}>
                            {t.direction}
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-zinc-300">
                          {t.quantity} <span className="text-[10px] text-zinc-500">({t.leverage}x)</span>
                        </td>
                        <td className="py-3 px-4 font-mono text-zinc-300">${t.entry_price}</td>
                        <td className="py-3 px-4 font-mono text-zinc-300">${t.exit_price}</td>
                        <td className="py-3 px-4 font-mono text-zinc-400">{formatDuration(t.duration_seconds)}</td>
                        <td className="py-3">
                          <span className="text-[11px] text-zinc-300 font-mono">
                            {t.exit_reason}
                          </span>
                        </td>
                        <td className={`py-3 px-4 font-mono font-bold text-right ${t.roe_pct >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                          {t.roe_pct >= 0 ? "+" : ""}{t.roe_pct}%
                        </td>
                        <td className={`py-3 px-4 font-mono font-black text-right ${t.realized_pnl >= 0 ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                          {formatUsdt(t.realized_pnl)} USDT
                        </td>
                        <td className="py-3 px-4 font-mono text-zinc-400 text-[11px] text-right">
                          {t.closed_at ? formatIST(t.closed_at) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
