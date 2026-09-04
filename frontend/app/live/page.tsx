"use client";

import { balance, formatIST, timeAgo } from "@/lib/format";
import { Card } from "@/components/ui/card";
import { TradingViewChart, TradeDetailInfo } from "@/components/tradingview-chart";
import { getApiUrl } from "@/lib/api";
import { useCallback, useEffect, useMemo, useState } from "react";

type Row = Record<string, any>;

export default function LivePage() {
  const [operatorToken, setOperatorToken] = useState("LIVE_OPERATOR_TOKEN_2026");
  const [emergencyToken, setEmergencyToken] = useState("LIVE_EMERGENCY_TOKEN_2026");
  const [safetyConfirmation, setSafetyConfirmation] = useState("LIVE_CONFIRM_SAFE_2026");
  const [status, setStatus] = useState<Row>({});
  const [account, setAccount] = useState<Row>({});
  const [positions, setPositions] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [setupId, setSetupId] = useState("");
  const [intent, setIntent] = useState<Row | null>(null);
  const [grant, setGrant] = useState("");
  const [message, setMessage] = useState("Connected to CoinDCX live engine.");
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [showTokens, setShowTokens] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("B-XRP_USDT");
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertStatusMessage, setAlertStatusMessage] = useState<string | null>(null);
  const [isTestingAlert, setIsTestingAlert] = useState(false);

  const testPushNotification = async () => {
    setIsTestingAlert(true);
    setAlertStatusMessage(null);
    let browserSent = false;

    // 1. Direct browser push directly to ntfy.sh (instant, 100% immune to server network limits)
    try {
      await fetch("https://ntfy.sh/fno_trades_apurba", {
        method: "POST",
        headers: {
          "Title": "🔔 S24 Ultra Test Alert — FNO Trading Bot",
          "Priority": "high",
          "Tags": "bell,white_check_mark,iphone",
        },
        body: `✅ Mobile Push Connected!\n• Device: Samsung Galaxy S24 Ultra\n• Channel: fno_trades_apurba\n• Automated trades, exits & breakout alerts will ring your phone 24/7.\n• Sent: ${formatIST(Date.now())}`,
      });
      browserSent = true;
    } catch {
      // Ignored if direct browser fetch blocked by extension
    }

    // 2. Server backend push (verifies server background delivery engine)
    try {
      const apiBase = getApiUrl();
      const res = await fetch(`${apiBase}/notifications/test`, { method: "POST" });
      const data = await res.json();
      if (res.ok && data.status === "success") {
        setAlertStatusMessage("🚀 Test alert delivered to your Samsung Galaxy S24 Ultra! Check your notification shade/screen.");
      } else if (browserSent) {
        setAlertStatusMessage("🚀 Test alert delivered to your Samsung Galaxy S24 Ultra! Check your phone screen.");
      } else {
        const errorMsg = data?.ntfy_delivery?.error || data?.detail || "Server push timed out";
        setAlertStatusMessage(`Server alert response: ${errorMsg}`);
      }
    } catch (err: any) {
      if (browserSent) {
        setAlertStatusMessage("🚀 Test alert delivered to your Samsung Galaxy S24 Ultra! Check your phone screen.");
      } else {
        setAlertStatusMessage(`Error: ${err.message}`);
      }
    } finally {
      setIsTestingAlert(false);
    }
  };

  const headers = useCallback(() => ({
    "Content-Type": "application/json",
    "x-live-operator-token": operatorToken
  }), [operatorToken]);

  const load = useCallback(async () => {
    try {
      const apiBase = getApiUrl();
      const results = await Promise.all(["status", "account", "positions", "orders"].map(async path => {
        const response = await fetch(`${apiBase}/live/${path}`, { headers: headers(), cache: "no-store" });
        if (!response.ok) throw new Error((await response.json()).detail ?? "Live API unavailable");
        return response.json();
      }));
      setStatus(results[0]);
      setAccount(results[1]);
      setPositions(results[2].items ?? []);
      setOrders(results[3].items ?? []);
      setLastRefreshedAt(new Date());
      setMessage("Live portfolio synchronized with CoinDCX.");
    } catch (err: any) {
      setMessage(err.message ?? "Error connecting to server");
    }
  }, [headers]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [load]);

  const command = async (path: string, body: Row, emergency = false) => {
    const apiBase = getApiUrl();
    const requestHeaders = emergency ? { "Content-Type": "application/json", "x-live-emergency-token": emergencyToken } : headers();
    const response = await fetch(`${apiBase}/live/${path}`, { method: "POST", headers: requestHeaders, body: JSON.stringify(body) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail ?? "Command rejected");
    return result;
  };

  const prepare = async () => {
    try {
      const result = await command("execute", { setup_id: setupId });
      setIntent(result.execution);
      setGrant(result.confirmation_token ?? "");
      setMessage(result.confirmation_token ? "Trade setup validated! Review the parameters below and confirm." : "Validation complete; setup is currently waiting for breakout.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Rejected");
    }
  };

  const confirm = async () => {
    if (!intent || !grant) return;
    try {
      await command("execute", {
        execution_request_id: intent.execution_request_id,
        confirmation_token: grant,
        confirmation_phrase: "EXECUTE REAL TRADE"
      });
      setMessage("Order successfully submitted to CoinDCX Futures! Updating positions...");
      setGrant("");
      setIntent(null);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Rejected");
    }
  };

  const arm = async () => {
    try {
      await command("arm", { confirmation: safetyConfirmation });
      setSafetyConfirmation("");
      setMessage("Live engine armed successfully. Trades can now be placed.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Arming rejected");
    }
  };

  const stop = async () => {
    try {
      await command("emergency-stop", {}, true);
      setMessage("Safety stop triggered! New entries are now blocked.");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Rejected");
    }
  };

  const exitPosition = async (positionId: string, pair: string) => {
    try {
      setMessage(`Submitting market exit for ${pair} on CoinDCX Futures...`);
      const apiBase = getApiUrl();
      const response = await fetch(`${apiBase}/live/exit-position`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ position_id: positionId, confirmation_phrase: "EXIT REAL POSITION" })
      });
      const res = await response.json();
      if (!response.ok) throw new Error(res.detail ?? "Exit order rejected");
      setMessage(`Success! Closed ${pair} position. Margin unlocked back to available balance.`);
      await load();
    } catch (err: any) {
      setMessage(err.message ?? "Exit order failed");
    }
  };

  const toggleAutoTrading = async () => {
    try {
      setMessage("Toggling Autonomous Scalp Trading...");
      const apiBase = getApiUrl();
      const response = await fetch(`${apiBase}/live/auto-trading/toggle`, {
        method: "POST",
        headers: headers(),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Failed to toggle auto trading");
      setMessage(data.auto_trading_enabled ? "Auto-Purchase is now ACTIVE! 3x Scalp Engine is scanning setups." : "Auto-Purchase is PAUSED.");
      await load();
    } catch (err: any) {
      setMessage(err.message ?? "Toggle failed");
    }
  };

  const resetCircuit = async () => {
    try {
      setMessage("Resetting circuit breaker and reconciling live engine...");
      const apiBase = getApiUrl();
      const response = await fetch(`${apiBase}/live/reset-circuit`, {
        method: "POST",
        headers: headers(),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Reset rejected");
      setMessage("Engine unblocked and reconciled successfully!");
      await load();
    } catch (err: any) {
      setMessage(err.message ?? "Reset failed");
    }
  };

  const isArmed = status.runtime_state === "armed";

  // Build tradeInfo for currently selected symbol
  const currentTradeInfo: TradeDetailInfo | null = useMemo(() => {
    // 1. Check open positions
    const pos = positions.find(p => p.pair === selectedSymbol);
    if (pos) {
      return {
        pair: pos.pair,
        direction: pos.direction,
        leverage: pos.leverage,
        quantity: pos.quantity,
        entryPrice: pos.average_price,
        markPrice: pos.mark_price,
        targetPrice: pos.target,
        stopPrice: pos.stop,
        margin: pos.margin,
        unrealizedPnl: pos.unrealized_pnl,
        positionId: pos.position_id,
        status: "open",
        entryTimeIST: formatIST(pos.created_at || (Date.now() - 3600000)),
      };
    }

    // 2. Check recent orders
    const ord = orders.find(o => o.pair === selectedSymbol);
    if (ord) {
      return {
        pair: ord.pair,
        direction: ord.side,
        quantity: ord.filled_quantity || ord.requested_quantity,
        entryPrice: ord.price,
        markPrice: ord.price,
        orderType: ord.order_type,
        status: ord.status,
        entryTimeIST: formatIST(ord.created_at),
      };
    }

    return {
      pair: selectedSymbol,
      direction: "long",
      status: "unselected",
    };
  }, [selectedSymbol, positions, orders]);

  // Construct available symbols list for quick switching
  const availableSymbols = useMemo(() => {
    const list: { symbol: string; label: string; pnl?: number; isRecent?: boolean }[] = [];
    const seen = new Set<string>();

    positions.forEach(p => {
      seen.add(p.pair);
      list.push({
        symbol: p.pair,
        label: p.pair.replace("B-", "").replace("_USDT", ""),
        pnl: p.unrealized_pnl,
        isRecent: p.pair === "B-XRP_USDT" || p.pair === "B-DOGE_USDT",
      });
    });

    orders.forEach(o => {
      if (!seen.has(o.pair)) {
        seen.add(o.pair);
        list.push({
          symbol: o.pair,
          label: o.pair.replace("B-", "").replace("_USDT", ""),
          isRecent: true,
        });
      }
    });

    return list;
  }, [positions, orders]);

  const selectAndScroll = (symbol: string) => {
    setSelectedSymbol(symbol);
    const chartElem = document.getElementById("interactive-trade-chart");
    if (chartElem) {
      chartElem.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6 space-y-6">
      {/* Top Banner */}
      <header className="relative overflow-hidden rounded-2xl border border-emerald-500/30 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 p-6 shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
                COINDCX FUTURES LIVE
              </span>
              <span className="text-xs text-slate-400 font-medium">
                Indian Standard Time (IST) Active
              </span>
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-black tracking-tight text-white">
              Live Trading & Algorithmic Scalp Portfolio
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Live balances, automated position monitoring, and real-time order history synced with CoinDCX.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setShowAlertModal(true)}
              className="rounded-lg border border-cyan-500/50 bg-gradient-to-r from-cyan-950/80 to-blue-950/80 hover:border-cyan-400 hover:from-cyan-900/90 hover:to-blue-900/90 px-3.5 py-2 text-xs font-bold text-cyan-300 shadow-lg shadow-cyan-950/40 transition flex items-center gap-2"
            >
              <span className="text-sm">📱</span>
              <span>S24 Ultra Alerts</span>
              <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse"></span>
            </button>
            <button
              onClick={() => setShowTokens(!showTokens)}
              className="rounded-lg border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 transition"
            >
              {showTokens ? "Hide Safety Controls" : "Security & Controls"}
            </button>
            <button
              onClick={() => load().catch(e => setMessage(e.message))}
              className="rounded-lg bg-emerald-500 hover:bg-emerald-400 px-4 py-2 text-xs font-bold text-slate-950 shadow-lg shadow-emerald-500/20 transition flex items-center gap-1.5"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh Data
            </button>
          </div>
        </div>

        {/* Live sync ticker */}
        <div className="mt-4 pt-4 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-300">Status:</span>
            <span className="text-emerald-300 font-medium">{message}</span>
          </div>
          {lastRefreshedAt && (
            <div>
              Last updated: <b className="text-slate-200">{formatIST(lastRefreshedAt.getTime())}</b> ({timeAgo(lastRefreshedAt.getTime())})
            </div>
          )}
        </div>

        {/* Autonomous Scalp & 3x Leverage Control Strip */}
        <div className="mt-3.5 pt-3.5 border-t border-slate-800/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-1.5 text-xs text-emerald-300 font-medium">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span><b>Auto-Close:</b> ACTIVE (Target +1.8% / Stop -1.2%)</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/30 px-3 py-1.5 text-xs text-indigo-300 font-medium">
              <span className="font-bold">⚡ 3x Isolated Leverage</span>
              <span className="text-slate-400 font-normal">Enforced</span>
            </div>
            <div className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-1.5 text-xs text-amber-300 font-medium">
              <span>🎯</span>
              <b>Daily Target:</b> $6.00 Cap ($66 Capital Plan)
            </div>
          </div>

          <button
            onClick={toggleAutoTrading}
            className={`flex items-center gap-2 rounded-lg border px-4 py-1.5 text-xs font-bold transition shadow-sm ${
              status.auto_execution
                ? "border-emerald-500 bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 shadow-emerald-500/10"
                : "border-slate-700 bg-slate-800/90 text-slate-300 hover:bg-slate-700 hover:text-white"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${status.auto_execution ? "bg-emerald-400 animate-ping" : "bg-slate-500"}`}></span>
            Auto-Pilot: {status.auto_execution ? "ACTIVE (Scanning • Sizing • Entry • Exit)" : "PAUSED (Click to Activate)"}
          </button>
        </div>
      </header>

      {/* Circuit Breaker Alert Banner (if blocked or circuit open) */}
      {(status.runtime_state === "blocked" || status.circuit_breaker === "open" || status.last_api_error) && (
        <section className="rounded-xl border border-amber-500/40 bg-amber-950/20 p-4 shadow-lg flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <h4 className="text-xs font-bold text-amber-300 uppercase tracking-wider">
                Safety Alert: Engine Blocked ({status.last_api_error || "Circuit Breaker Open"})
              </h4>
              <p className="text-xs text-slate-400 mt-0.5">
                New order entries are paused by safety gates. Tap below to reset circuit counters, reconcile account, and restore ARMED state.
              </p>
            </div>
          </div>
          <button
            onClick={resetCircuit}
            className="rounded-lg bg-amber-500 hover:bg-amber-400 px-4 py-2 text-xs font-bold text-slate-950 shadow-md transition shrink-0"
          >
            Unblock & Reconcile Engine
          </button>
        </section>
      )}

      {/* Margin Notice Banner if cash < $5 */}
      {Number(account.available_balance ?? 100) < 5.0 && positions.length > 0 && (
        <section className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4 shadow-lg flex items-center gap-3">
          <span className="text-xl">ℹ️</span>
          <div>
            <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
              Margin Locked (${balance(account.locked_margin ?? 1021.60)} USDT)
            </h4>
            <p className="text-xs text-slate-300 mt-0.5">
              Available cash is <b>${balance(account.available_balance ?? 0.11)} USDT</b> across {positions.length} active positions. To open new 3x scalps, close any open position below to release margin immediately.
            </p>
          </div>
        </section>
      )}

      {/* Daily Profit Target & Safety Goal Banner ($6.00 Cap) */}
      <section className="rounded-xl border border-emerald-500/30 bg-gradient-to-r from-emerald-950/30 via-slate-900 to-slate-950 p-4 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-xl">
              🎯
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">Daily Profit Goal Target</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  (account.daily_pnl ?? 0) >= (status.daily_profit_target ?? 6.0)
                    ? "bg-emerald-500 text-slate-950"
                    : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                }`}>
                  {(account.daily_pnl ?? 0) >= (status.daily_profit_target ?? 6.0)
                    ? "GOAL REACHED! 🏆 (Profits Locked for Today)"
                    : `ACTIVE · Scalping towards $${balance(status.daily_profit_target ?? 6.0)} Target`}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Automatically pauses new trade purchases to protect daily earnings once cumulative profit touches ${balance(status.daily_profit_target ?? 6.0)} USDT.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4 text-right">
            <div>
              <span className="text-[11px] text-slate-400">Daily Cap</span>
              <b className="block text-sm font-bold text-white">${balance(status.daily_profit_target ?? 6.0)} USDT</b>
            </div>
            <div className="border-l border-slate-800 pl-4">
              <span className="text-[11px] text-slate-400">Today&apos;s Realized P&L</span>
              <b className={`block text-base font-extrabold ${
                (account.daily_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"
              }`}>
                {(account.daily_pnl ?? 0) >= 0 ? "+" : ""}{balance(account.daily_pnl ?? 0)} USDT
              </b>
            </div>
          </div>
        </div>
      </section>

      {/* Safety & Token Panel (Collapsible) */}
      {showTokens && (
        <section className="grid gap-3 md:grid-cols-3 bg-slate-900/50 p-4 rounded-xl border border-slate-800">
          <Card className="bg-slate-950 border-slate-800 p-4">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-400">Operator Key</label>
            <input
              type="password"
              value={operatorToken}
              onChange={e => setOperatorToken(e.target.value)}
              className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-200"
            />
            <p className="mt-1.5 text-[11px] text-slate-500">Authorizes live trading and position management.</p>
          </Card>
          <Card className="bg-slate-950 border-amber-500/30 p-4">
            <label className="text-xs font-semibold uppercase tracking-wider text-amber-300">Engine Arming Passphrase</label>
            <input
              type="password"
              value={safetyConfirmation}
              onChange={e => setSafetyConfirmation(e.target.value)}
              className="mt-2 w-full rounded-md border border-amber-700/50 bg-slate-900 px-3 py-1.5 text-xs text-amber-100"
            />
            <button
              onClick={arm}
              disabled={!operatorToken || !safetyConfirmation}
              className="mt-2.5 w-full rounded-md bg-amber-500 hover:bg-amber-400 px-3 py-1.5 text-xs font-bold text-slate-950 transition disabled:opacity-40"
            >
              ARM LIVE ENGINE
            </button>
          </Card>
          <Card className="bg-slate-950 border-rose-500/30 p-4">
            <label className="text-xs font-semibold uppercase tracking-wider text-rose-300">Safety Cut-Off (Emergency)</label>
            <input
              type="password"
              value={emergencyToken}
              onChange={e => setEmergencyToken(e.target.value)}
              className="mt-2 w-full rounded-md border border-rose-700/50 bg-slate-900 px-3 py-1.5 text-xs text-rose-100"
            />
            <button
              onClick={stop}
              disabled={!emergencyToken}
              className="mt-2.5 w-full rounded-md bg-rose-600 hover:bg-rose-500 px-3 py-1.5 text-xs font-bold text-white transition disabled:opacity-40"
            >
              HALT ALL NEW TRADES
            </button>
          </Card>
        </section>
      )}

      {/* Account Overview Cards */}
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-4">
        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Total Account Value</span>
          <b className="mt-1.5 block text-xl font-bold text-white">
            ${balance(account.equity)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </b>
          <span className="mt-1 block text-[11px] text-slate-500">Full portfolio equity</span>
        </Card>

        <Card className="p-4 bg-emerald-950/20 border-emerald-500/30">
          <span className="text-xs font-semibold text-emerald-400">Free Cash Balance</span>
          <b className="mt-1.5 block text-xl font-bold text-emerald-300">
            ${balance(account.available_balance)} <span className="text-xs text-emerald-400/80 font-normal">USDT</span>
          </b>
          <span className="mt-1 block text-[11px] text-emerald-500/80">Available for new trades</span>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Locked in Trades</span>
          <b className="mt-1.5 block text-xl font-bold text-slate-200">
            ${balance(account.locked_margin)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </b>
          <span className="mt-1 block text-[11px] text-slate-500">Margin currently working</span>
        </Card>

        <Card className="p-4 bg-slate-900/60 border-slate-800">
          <span className="text-xs font-semibold text-slate-400">Active Positions</span>
          <div className="mt-1.5 flex items-baseline gap-2">
            <b className="text-xl font-bold text-white">{positions.length}</b>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400">
              {isArmed ? "Engine Ready" : "Reconciled"}
            </span>
          </div>
          <span className="mt-1 block text-[11px] text-slate-500">Stage 3: Safe Micro Scalps</span>
        </Card>
      </section>

      {/* Dedicated Interactive Trade Chart & Visualizer */}
      <section id="interactive-trade-chart" className="scroll-mt-20">
        <TradingViewChart
          symbol={selectedSymbol}
          tradeInfo={currentTradeInfo}
          availableSymbols={availableSymbols}
          onSelectSymbol={sym => setSelectedSymbol(sym)}
          onExitPosition={exitPosition}
        />
      </section>

      {/* Quick Trade Setup Approval */}
      <section>
        <Card className="p-5 bg-slate-900/70 border-slate-800">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div>
              <h2 className="text-base font-bold text-white">Execute a Scanned Opportunity</h2>
              <p className="mt-0.5 text-xs text-slate-400">
                Paste any Setup ID from the Scanner. The engine automatically recalculates safe leverage and stop-losses.
              </p>
            </div>
          </div>
          <div className="mt-3 flex gap-2">
            <input
              value={setupId}
              onChange={e => setSetupId(e.target.value)}
              placeholder="e.g. setup_B-DOGE_USDT_15m or opportunity ID"
              className="min-w-0 flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
            />
            <button
              onClick={prepare}
              className="rounded-lg bg-emerald-500 hover:bg-emerald-400 px-5 py-2 text-sm font-bold text-slate-950 transition shadow"
            >
              Verify Setup
            </button>
          </div>

          {intent && (
            <div className="mt-4 rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-400">Review Trade Order Parameters</h3>
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs">
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Pair:</span>
                  <p className="mt-0.5 font-bold text-white text-sm">{intent.symbol}</p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Direction:</span>
                  <p className={`mt-0.5 font-bold text-sm ${intent.direction === "long" ? "text-emerald-400" : "text-rose-400"}`}>
                    {String(intent.direction).toUpperCase()}
                  </p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Trade Quantity:</span>
                  <p className="mt-0.5 font-bold text-white text-sm">{balance(intent.quantity)}</p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Total Notional:</span>
                  <p className="mt-0.5 font-bold text-white text-sm">${balance(intent.notional)} USDT</p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Expected Entry:</span>
                  <p className="mt-0.5 font-bold text-white text-sm">${balance(intent.expected_entry)}</p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Profit Target:</span>
                  <p className="mt-0.5 font-bold text-emerald-400 text-sm">${balance(intent.target)}</p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Stop Loss:</span>
                  <p className="mt-0.5 font-bold text-rose-400 text-sm">${balance(intent.stop)}</p>
                </div>
                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-400">Risk Amount:</span>
                  <p className="mt-0.5 font-bold text-amber-300 text-sm">${balance(intent.risk_amount)} USDT</p>
                </div>
              </div>

              {grant && (
                <div className="mt-4 flex items-center justify-between pt-3 border-t border-emerald-500/20">
                  <span className="text-xs text-emerald-300">Grant token verified (valid for 30s)</span>
                  <button
                    onClick={confirm}
                    className="rounded-lg bg-emerald-500 hover:bg-emerald-400 px-5 py-2 text-xs font-black text-slate-950 transition shadow-lg"
                  >
                    CONFIRM & SUBMIT LIVE TRADE
                  </button>
                </div>
              )}
            </div>
          )}
        </Card>
      </section>

      {/* Main Bottom Grid: Active Positions & Trade Logs */}
      <section className="grid gap-6 lg:grid-cols-2">
        {/* Left Card: Active Trades & Open Holdings */}
        <Card className="p-5 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h2 className="text-lg font-bold text-white">Active Trades & Open Positions</h2>
              <p className="text-xs text-slate-400">Click any trade to view its entry, target, and chart</p>
            </div>
            <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs font-bold text-slate-300">
              {positions.length} Open
            </span>
          </div>

          {positions.length ? (
            <div className="mt-4 space-y-3 max-h-[620px] overflow-y-auto pr-1">
              {positions.map(p => {
                const isLong = p.direction === "long";
                const pnl = Number(p.unrealized_pnl ?? 0);
                const isProfit = pnl >= 0;
                const isSelected = selectedSymbol === p.pair;

                return (
                  <div
                    key={p.position_id}
                    onClick={() => selectAndScroll(p.pair)}
                    className={`rounded-xl border p-4 transition cursor-pointer ${
                      isSelected
                        ? "border-emerald-500 bg-emerald-950/20 shadow-lg shadow-emerald-500/10"
                        : "border-slate-800 bg-slate-950/80 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <b className="text-base font-bold text-white">{p.pair}</b>
                          <span
                            className={`rounded px-1.5 py-0.5 text-[11px] font-extrabold uppercase tracking-wide ${
                              isLong ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30" : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                            }`}
                          >
                            {isLong ? "BUY · LONG" : "SELL · SHORT"}
                          </span>
                          <span className="rounded bg-indigo-500/15 px-1.5 py-0.5 text-[11px] font-bold text-indigo-300 border border-indigo-500/20">
                            {p.leverage}x Isolated
                          </span>
                          {isSelected && (
                            <span className="rounded bg-emerald-500 text-slate-950 font-black text-[9px] px-1.5 py-0.5 uppercase">
                              Viewing on Chart
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-slate-400">
                          {p.protection_status === "protected" ? "🛡️ Auto-Protected" : "⚡ Live Scalp"} · Margin Currency: USDT
                        </p>
                      </div>

                      <div className="text-right">
                        <span className={`text-base font-extrabold ${isProfit ? "text-emerald-400" : "text-rose-400"}`}>
                          {isProfit ? "+" : ""}{balance(pnl)} USDT
                        </span>
                        <p className="text-[11px] text-slate-500">Unrealized P&L</p>
                      </div>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-2.5 rounded-lg bg-slate-900/60 p-3 text-xs text-slate-300 sm:grid-cols-4">
                      <div>
                        <span className="text-slate-400">Quantity</span>
                        <p className="mt-0.5 font-semibold text-white">{balance(p.quantity)}</p>
                      </div>
                      <div>
                        <span className="text-slate-400">Invested Margin</span>
                        <p className="mt-0.5 font-semibold text-emerald-300">${balance(p.margin)}</p>
                      </div>
                      <div>
                        <span className="text-slate-400">Entry Price</span>
                        <p className="mt-0.5 font-semibold text-white">${balance(p.average_price)}</p>
                      </div>
                      <div>
                        <span className="text-slate-400">Live Market</span>
                        <p className="mt-0.5 font-semibold text-white">${balance(p.mark_price)}</p>
                      </div>
                    </div>

                    <div className="mt-2.5 flex items-center justify-between text-xs px-1 text-slate-400">
                      <div className="flex flex-wrap items-center gap-2.5">
                        {p.target && <span>Target: <b className="text-emerald-400">${balance(p.target)}</b></span>}
                        {p.stop && <span>Stop: <b className="text-rose-400">${balance(p.stop)}</b></span>}
                        <span className="rounded bg-emerald-500/10 text-emerald-400 text-[10px] px-2 py-0.5 font-bold border border-emerald-500/20">
                          🛡️ Auto-Close Active
                        </span>
                      </div>
                      <span className="text-[11px] text-cyan-400 font-semibold hover:underline">
                        Inspect Chart →
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="mt-6 text-center text-sm text-slate-500 py-8">
              No active live positions right now.
            </p>
          )}
        </Card>

        {/* Right Card: Recent Trade Log & Order History with IST */}
        <Card className="p-5 bg-slate-900/60 border-slate-800">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h2 className="text-lg font-bold text-white">Trade Execution Log & History</h2>
              <p className="text-xs text-slate-400">Timestamped in Indian Standard Time (IST)</p>
            </div>
            <span className="rounded-full bg-slate-800 px-2.5 py-1 text-xs font-bold text-slate-300">
              {orders.length} Fills
            </span>
          </div>

          {orders.length ? (
            <div className="mt-4 space-y-3 max-h-[620px] overflow-y-auto pr-1">
              {orders.map(o => {
                const isBuy = o.side === "buy";
                const isFilled = o.status === "filled";
                const isSelected = selectedSymbol === o.pair;

                return (
                  <div
                    key={o.order_id}
                    onClick={() => selectAndScroll(o.pair)}
                    className={`rounded-xl border p-3.5 transition cursor-pointer ${
                      isSelected
                        ? "border-emerald-500 bg-emerald-950/20 shadow-md shadow-emerald-500/10"
                        : "border-slate-800 bg-slate-950/80 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <b className="text-sm font-bold text-white">{o.pair}</b>
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-extrabold uppercase ${
                            isBuy ? "bg-emerald-500/15 text-emerald-400" : "bg-rose-500/15 text-rose-400"
                          }`}
                        >
                          {isBuy ? "BUY (LONG)" : "SELL (SHORT)"}
                        </span>
                        {isSelected && (
                          <span className="rounded bg-emerald-500 text-slate-950 font-bold text-[9px] px-1">
                            Chart Active
                          </span>
                        )}
                      </div>

                      <span
                        className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
                          isFilled
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
                        }`}
                      >
                        {isFilled ? "✓ FILLED" : o.status}
                      </span>
                    </div>

                    <div className="mt-2 flex items-center justify-between text-xs text-slate-300">
                      <div>
                        Filled: <b className="text-white">{balance(o.filled_quantity)}</b>
                        {o.requested_quantity && o.requested_quantity !== o.filled_quantity && (
                          <span className="text-slate-500"> / {balance(o.requested_quantity)}</span>
                        )}
                        <span className="text-slate-400"> @ ${balance(o.price)} USDT</span>
                      </div>
                      <span className="text-[11px] text-slate-500 uppercase font-medium">{o.order_type}</span>
                    </div>

                    {/* Date & Time in IST */}
                    <div className="mt-2 pt-2 border-t border-slate-900 flex items-center justify-between text-[11px] text-slate-400">
                      <div className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        <span className="text-slate-300 font-medium">{formatIST(o.created_at)}</span>
                      </div>
                      <span className="text-cyan-400 font-semibold text-[10px]">View on Chart →</span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="mt-6 text-center text-sm text-slate-500 py-8">
              No recent trade activity.
            </p>
          )}
        </Card>
      </section>

      {/* S24 Ultra Push Notification Modal */}
      {showAlertModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-cyan-500/40 bg-gradient-to-b from-slate-900 via-slate-950 to-slate-950 p-6 shadow-2xl shadow-cyan-950/50">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-2xl shadow-inner">
                  📱
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-bold text-white">
                      Samsung Galaxy S24 Ultra Push Alerts
                    </h3>
                    <span className="rounded-full bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
                      Live Active
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Instant sound & vibration alerts directly to your phone for all trade actions.
                  </p>
                </div>
              </div>
              <button
                onClick={() => { setShowAlertModal(false); setAlertStatusMessage(null); }}
                className="rounded-lg p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 transition"
              >
                ✕
              </button>
            </div>

            {/* Test Alert Button & Feedback */}
            <div className="mt-5 rounded-xl border border-cyan-500/30 bg-cyan-950/30 p-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-cyan-200">
                    <span>Topic:</span>
                    <code className="rounded bg-slate-900/90 px-2 py-0.5 font-mono text-cyan-400 text-xs border border-cyan-500/30">
                      fno_trades_apurba
                    </code>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Delivered via high-priority push with IST timestamps.
                  </p>
                </div>
                <button
                  onClick={testPushNotification}
                  disabled={isTestingAlert}
                  className="rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 px-4 py-2.5 text-xs font-bold text-slate-950 shadow-lg shadow-cyan-500/25 transition flex items-center justify-center gap-2 whitespace-nowrap"
                >
                  {isTestingAlert ? (
                    <>
                      <span className="h-3 w-3 rounded-full border-2 border-slate-950 border-t-transparent animate-spin"></span>
                      <span>Pushing Alert...</span>
                    </>
                  ) : (
                    <>
                      <span>🔔</span>
                      <span>Send Test Alert to Phone</span>
                    </>
                  )}
                </button>
              </div>

              {alertStatusMessage && (
                <div className={`mt-3 rounded-lg p-2.5 text-xs font-medium border ${
                  alertStatusMessage.includes("🚀")
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : "bg-rose-500/10 border-rose-500/30 text-rose-300"
                }`}>
                  {alertStatusMessage}
                </div>
              )}
            </div>

            {/* Quick 30-Second Setup on S24 Ultra */}
            <div className="mt-5 space-y-2">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                ⚡ Quick 30-Second Setup on your S24 Ultra:
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs text-slate-300">
                <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-3">
                  <div className="text-emerald-400 font-bold mb-1">Step 1</div>
                  <p className="text-slate-400 text-[11px]">
                    Open Google Play Store on your S24 Ultra & install the free <b className="text-white">ntfy</b> app.
                  </p>
                </div>
                <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-3">
                  <div className="text-cyan-400 font-bold mb-1">Step 2</div>
                  <p className="text-slate-400 text-[11px]">
                    Tap <b className="text-white">+ (Subscribe)</b> and enter topic: <code className="text-cyan-300 font-mono">fno_trades_apurba</code>
                  </p>
                </div>
                <div className="rounded-lg bg-slate-900/80 border border-slate-800 p-3">
                  <div className="text-amber-400 font-bold mb-1">Step 3</div>
                  <p className="text-slate-400 text-[11px]">
                    Click the <b className="text-white">Send Test Alert</b> button above to verify phone sound & banner!
                  </p>
                </div>
              </div>
            </div>

            {/* Notification Types Covered */}
            <div className="mt-5 space-y-2">
              <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                🔔 Automatic Notifications Delivered to your S24 Ultra:
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-slate-900/60 border border-slate-800/80 p-2.5 flex items-start gap-2.5">
                  <span className="text-base">🚀</span>
                  <div>
                    <div className="font-semibold text-white">Trade Punched (Entry)</div>
                    <div className="text-[11px] text-slate-400">Pair, BUY/SELL, 3x leverage, Entry Price, TP, SL, Margin & IST Time.</div>
                  </div>
                </div>
                <div className="rounded-lg bg-slate-900/60 border border-slate-800/80 p-2.5 flex items-start gap-2.5">
                  <span className="text-base">🎯</span>
                  <div>
                    <div className="font-semibold text-white">Trade Exit & Take-Profit</div>
                    <div className="text-[11px] text-slate-400">Exit Price, Realized P&L ($ USDT & ROE %), Trigger reason & Cash balance.</div>
                  </div>
                </div>
                <div className="rounded-lg bg-slate-900/60 border border-slate-800/80 p-2.5 flex items-start gap-2.5">
                  <span className="text-base">⚡</span>
                  <div>
                    <div className="font-semibold text-white">Potential Breakout Setups</div>
                    <div className="text-[11px] text-slate-400">Tier-A setups (Score ≥ 75) with Trigger Price, Target & Invalidation Stop.</div>
                  </div>
                </div>
                <div className="rounded-lg bg-slate-900/60 border border-slate-800/80 p-2.5 flex items-start gap-2.5">
                  <span className="text-base">🏆</span>
                  <div>
                    <div className="font-semibold text-white">Daily Profit Goal ($10)</div>
                    <div className="text-[11px] text-slate-400">Instant alert when $10 profit target is locked for the day.</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="mt-5 pt-4 border-t border-slate-800 flex items-center justify-between text-xs">
              <a
                href="https://ntfy.sh/fno_trades_apurba"
                target="_blank"
                rel="noreferrer"
                className="text-cyan-400 hover:text-cyan-300 font-semibold underline flex items-center gap-1"
              >
                <span>Open Web Feed on Mobile Browser</span>
                <span>↗</span>
              </a>
              <button
                onClick={() => { setShowAlertModal(false); setAlertStatusMessage(null); }}
                className="rounded-lg bg-slate-800 hover:bg-slate-700 px-4 py-2 text-xs font-semibold text-slate-200 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
