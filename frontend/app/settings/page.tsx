"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

type MasterSwitchStatus = {
  master_enabled: boolean;
  emergency_stop_active: boolean;
  auto_trading_enabled: boolean;
  runtime_state: string;
  circuit_breaker_state: string;
  open_positions_count: number;
  open_positions: Array<{
    symbol: string;
    pnl: number;
    side: string;
    entry: number;
    mark: number;
    position_id: string;
  }>;
  today_pnl: number;
  today_profit: number;
  today_loss: number;
  capital_shield_active: boolean;
  max_concurrent_positions: number;
  min_24h_volume_usdt: number;
};

export default function SettingsPage() {
  const [status, setStatus] = useState<MasterSwitchStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [closePositionsChecked, setClosePositionsChecked] = useState(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [testAlertLoading, setTestAlertLoading] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const apiBase = getApiUrl();
      const res = await fetch(`${apiBase}/live/master-switch`, {
        headers: { "x-live-operator-token": "LIVE_OPERATOR_TOKEN_2026" },
        cache: "no-store",
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err: any) {
      console.error("Failed to fetch master switch status", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleToggleMasterSwitch = async (enable: boolean) => {
    if (!enable) {
      const confirmText = closePositionsChecked
        ? "EMERGENCY HALT: Are you sure you want to stop all automated operations AND close all active CoinDCX positions?"
        : "EMERGENCY HALT: Are you sure you want to freeze all automated trading operations?";
      if (!window.confirm(confirmText)) return;
    } else {
      if (!window.confirm("RESUME OPERATIONS: Are you sure you want to re-arm the scalper daemon and resume live trading?")) return;
    }

    try {
      setActionLoading(true);
      setActionMessage(enable ? "Resuming system operations..." : "Executing emergency halt...");
      const apiBase = getApiUrl();
      const res = await fetch(`${apiBase}/live/master-switch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-live-operator-token": "LIVE_OPERATOR_TOKEN_2026",
          "x-live-emergency-token": "LIVE_EMERGENCY_TOKEN_2026",
        },
        body: JSON.stringify({
          enabled: enable,
          close_open_positions: !enable && closePositionsChecked,
          operator_token: "LIVE_OPERATOR_TOKEN_2026",
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "Failed to update master switch");
      }

      const updated = await res.json();
      setStatus(updated);
      setActionMessage(
        enable
          ? "🟢 System resumed! Scalper daemon re-armed and operational."
          : `🔴 Emergency halt active! All trading halted.${closePositionsChecked ? " Open positions closed." : ""}`
      );
    } catch (err: any) {
      setActionMessage(`❌ Error: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleTestAlert = async () => {
    try {
      setTestAlertLoading(true);
      // Send directly to ntfy.sh
      await fetch("https://ntfy.sh/fno_scalp_apurba_2026_alerts", {
        method: "POST",
        headers: {
          "Title": "🔔 Master Switch Test Alert",
          "Priority": "default",
          "Tags": "bell,white_check_mark",
        },
        body: "Test notification from FNO Suite Settings. Alerts are functioning correctly!",
      });
      setActionMessage("✅ Test alert sent to your phone via ntfy.sh!");
    } catch (err: any) {
      setActionMessage(`❌ Notification error: ${err.message}`);
    } finally {
      setTestAlertLoading(false);
    }
  };

  const isHalted = status ? !status.master_enabled || status.emergency_stop_active : false;

  return (
    <main className="mx-auto max-w-[1400px] p-4 sm:p-8 space-y-8">
      {/* Header Banner */}
      <header className="cred-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.9)]">
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-[#FF3366]/10 blur-3xl"></div>
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-[#00F5A0]/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.08] px-3 py-1 text-[11px] font-black tracking-wider uppercase text-zinc-300 border border-white/[0.12]">
                <span className={`h-2 w-2 rounded-full ${isHalted ? "bg-rose-500 animate-ping" : "bg-[#00F5A0] animate-pulse"}`}></span>
                System Settings & Kill Switch
              </span>
              <span className="text-xs text-zinc-500 font-mono">Zero-Latency Emergency Controls</span>
            </div>
            <h1 className="mt-2 text-2xl sm:text-4xl font-black tracking-tight text-white">
              Master System Control
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-zinc-400">
              Instantly pause all automated trading, emergency exit open contracts, or resume live operations without touching the server.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/live"
              className="rounded-xl border border-white/[0.1] bg-white/[0.04] px-4 py-2 text-xs font-bold text-zinc-300 hover:bg-white/[0.08] hover:text-white transition"
            >
              ← Back to Live Portfolio
            </Link>
          </div>
        </div>
      </header>

      {/* Action Notification Message */}
      {actionMessage && (
        <div className={`p-4 rounded-2xl border text-xs sm:text-sm font-semibold flex items-center justify-between transition ${
          actionMessage.includes("🔴") || actionMessage.includes("❌")
            ? "border-rose-500/40 bg-rose-500/10 text-rose-300"
            : "border-[#00F5A0]/40 bg-[#00F5A0]/10 text-[#00F5A0]"
        }`}>
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-xs opacity-60 hover:opacity-100">Dismiss</button>
        </div>
      )}

      {/* ── MASTER EMERGENCY KILL SWITCH HERO CARD ── */}
      <Card className={`relative overflow-hidden border-2 transition-all p-6 sm:p-10 ${
        isHalted
          ? "border-rose-500 bg-gradient-to-br from-rose-950/40 via-[#0a0507] to-[#0c0c10] shadow-[0_0_80px_rgba(244,63,94,0.3)]"
          : "border-[#00F5A0]/40 bg-gradient-to-br from-[#00F5A0]/5 via-[#0c0c10] to-[#0c0c10] shadow-[0_0_60px_rgba(0,245,160,0.15)]"
      }`}>
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-8">
          <div className="space-y-3 max-w-2xl">
            <div className="flex items-center gap-3">
              <div className={`h-4 w-4 rounded-full ${isHalted ? "bg-rose-500 animate-ping" : "bg-[#00F5A0] animate-pulse"}`}></div>
              <span className="font-mono text-xs uppercase tracking-[0.2em] text-zinc-400 font-bold">
                Operational Status
              </span>
            </div>

            <h2 className={`text-2xl sm:text-4xl font-black tracking-tight ${
              isHalted ? "text-rose-400" : "text-[#00F5A0]"
            }`}>
              {isHalted ? "EMERGENCY HALT ACTIVE" : "SYSTEM ARMED & OPERATIONAL"}
            </h2>

            <p className="text-xs sm:text-sm text-zinc-300 leading-relaxed">
              {isHalted
                ? "All algorithmic trade execution is completely frozen. The auto-scalper daemon will NOT scan, evaluate, or punch any orders until explicitly resumed."
                : "The autonomous scalper daemon is armed and actively scanning for high-volume 5m momentum setups. Stop losses, trailing profit locks, and safety guardrails are active."}
            </p>

            {/* Emergency Option Checkbox (only when armed) */}
            {!isHalted && (
              <div className="pt-2">
                <label className="inline-flex items-center gap-2.5 text-xs text-rose-300 font-medium cursor-pointer select-none bg-rose-500/10 border border-rose-500/20 px-3 py-2 rounded-xl hover:bg-rose-500/15 transition">
                  <input
                    type="checkbox"
                    checked={closePositionsChecked}
                    onChange={(e) => setClosePositionsChecked(e.target.checked)}
                    className="rounded border-rose-500/40 text-rose-500 focus:ring-rose-500 h-4 w-4 bg-black"
                  />
                  <span>Emergency close all active CoinDCX positions upon halting</span>
                </label>
              </div>
            )}
          </div>

          {/* Large Action Toggle Button */}
          <div className="flex flex-col sm:flex-row items-center gap-4 shrink-0">
            {isHalted ? (
              <button
                onClick={() => handleToggleMasterSwitch(true)}
                disabled={actionLoading}
                className="w-full sm:w-auto px-8 py-5 rounded-2xl font-black text-sm uppercase tracking-wider bg-gradient-to-r from-[#00F5A0] to-[#00D9F5] text-black shadow-[0_0_40px_rgba(0,245,160,0.5)] hover:scale-105 active:scale-95 transition disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-3"
              >
                <span className="h-3 w-3 rounded-full bg-black"></span>
                <span>Resume Operations</span>
              </button>
            ) : (
              <button
                onClick={() => handleToggleMasterSwitch(false)}
                disabled={actionLoading}
                className="w-full sm:w-auto px-8 py-5 rounded-2xl font-black text-sm uppercase tracking-wider bg-gradient-to-r from-[#FF3366] via-rose-600 to-red-700 text-white shadow-[0_0_50px_rgba(255,51,102,0.6)] hover:scale-105 active:scale-95 transition disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center gap-3"
              >
                <span className="h-3 w-3 rounded-full bg-white animate-ping"></span>
                <span>Emergency Stop (Kill Switch)</span>
              </button>
            )}
          </div>
        </div>
      </Card>

      {/* ── SYSTEM PARAMETERS & LIVE STATUS GRID ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
        {/* Card 1: Scalper Daemon Status */}
        <Card className="space-y-2">
          <span className="text-[10px] font-mono uppercase text-zinc-500 tracking-wider">Scalper Daemon</span>
          <div className="flex items-center gap-2">
            <span className={`h-2.5 w-2.5 rounded-full ${status?.auto_trading_enabled ? "bg-[#00F5A0]" : "bg-rose-500"}`}></span>
            <span className="text-lg font-black text-white">
              {status?.auto_trading_enabled ? "Active (Looping)" : "Paused / Frozen"}
            </span>
          </div>
          <p className="text-[11px] text-zinc-400">Daemon evaluates every 10s when active.</p>
        </Card>

        {/* Card 2: Open Positions Capacity */}
        <Card className="space-y-2">
          <span className="text-[10px] font-mono uppercase text-zinc-500 tracking-wider">Simultaneous Scalps</span>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-black text-white">{status?.open_positions_count ?? 0}</span>
            <span className="text-xs font-mono text-zinc-400">/ 2 max concurrent</span>
          </div>
          <p className="text-[11px] text-zinc-400">
            {status?.open_positions && status.open_positions.length > 0
              ? status.open_positions.map(p => `${p.symbol} (${p.pnl >= 0 ? "+" : ""}${p.pnl} USDT)`).join(", ")
              : "No active open positions"}
          </p>
        </Card>

        {/* Card 3: Volume Floor Guard */}
        <Card className="space-y-2">
          <span className="text-[10px] font-mono uppercase text-zinc-500 tracking-wider">Min 24h Volume Floor</span>
          <div className="text-2xl font-black text-white font-mono">$10,000,000</div>
          <p className="text-[11px] text-zinc-400">Eliminates illiquid coins, wide spreads & slippage.</p>
        </Card>

        {/* Card 4: Today's Realized PnL */}
        <Card className="space-y-2">
          <span className="text-[10px] font-mono uppercase text-zinc-500 tracking-wider">Today's Realized PnL</span>
          <div className={`text-2xl font-black font-mono ${
            (status?.today_pnl ?? 0) >= 0 ? "text-[#00F5A0]" : "text-rose-400"
          }`}>
            {(status?.today_pnl ?? 0) >= 0 ? "+" : ""}{status?.today_pnl ?? "0.00"} USDT
          </div>
          <p className="text-[11px] text-zinc-400">
            Profit: +${status?.today_profit ?? 0} | Loss: -${status?.today_loss ?? 0}
          </p>
        </Card>
      </div>

      {/* ── QUICK SYSTEM UTILITIES ── */}
      <div className="space-y-4">
        <h3 className="text-lg font-black text-white tracking-wide">System Diagnostics & Tools</h3>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Tool 1: Test Notification */}
          <Card className="p-5 flex flex-col justify-between gap-4">
            <div>
              <div className="font-bold text-sm text-white flex items-center gap-2">
                <span>📱</span> Phone Alerts (ntfy.sh)
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                Dispatch an instant test notification to verify your mobile push setup.
              </p>
            </div>
            <button
              onClick={handleTestAlert}
              disabled={testAlertLoading}
              className="w-full py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs font-bold text-zinc-200 hover:bg-white/[0.08] hover:text-white transition disabled:opacity-50"
            >
              {testAlertLoading ? "Sending..." : "Send Test Push Alert"}
            </button>
          </Card>

          {/* Tool 2: Direct Reconcile */}
          <Card className="p-5 flex flex-col justify-between gap-4">
            <div>
              <div className="font-bold text-sm text-white flex items-center gap-2">
                <span>🔄</span> Sync Exchange Orders
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                Poll CoinDCX account directly to synchronize live open positions & balances.
              </p>
            </div>
            <button
              onClick={fetchStatus}
              disabled={loading}
              className="w-full py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs font-bold text-zinc-200 hover:bg-white/[0.08] hover:text-white transition disabled:opacity-50"
            >
              {loading ? "Syncing..." : "Sync CoinDCX State"}
            </button>
          </Card>

          {/* Tool 3: CoinDCX External Terminal */}
          <Card className="p-5 flex flex-col justify-between gap-4">
            <div>
              <div className="font-bold text-sm text-white flex items-center gap-2">
                <span>⚡</span> CoinDCX Futures Terminal
              </div>
              <p className="text-xs text-zinc-400 mt-1">
                Open CoinDCX official derivatives exchange web terminal in a new tab.
              </p>
            </div>
            <a
              href="https://coindcx.com/derivatives/futures"
              target="_blank"
              rel="noreferrer"
              className="w-full py-2.5 rounded-xl border border-white/[0.1] bg-white/[0.04] text-xs font-bold text-zinc-200 hover:bg-white/[0.08] hover:text-white transition text-center inline-block"
            >
              Open CoinDCX Terminal ↗
            </a>
          </Card>
        </div>
      </div>
    </main>
  );
}
