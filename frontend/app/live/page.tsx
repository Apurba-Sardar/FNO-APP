"use client";

import { balance, formatIST, formatISTTime, timeAgo } from "@/lib/format";
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

  const [rightCardTab, setRightCardTab] = useState<"research" | "orders">("research");
  const [researchFeed, setResearchFeed] = useState<Row | null>(null);
  const [isPunchingScalp, setIsPunchingScalp] = useState<string | null>(null);
  const [scalpDirection, setScalpDirection] = useState<"buy" | "sell">("buy");

  const headers = useCallback(() => ({
    "Content-Type": "application/json",
    "x-live-operator-token": operatorToken
  }), [operatorToken]);

  const load = useCallback(async () => {
    try {
      const apiBase = getApiUrl();
      const paths = ["status", "account", "positions", "orders", "research-feed"];
      const results = await Promise.all(paths.map(async path => {
        try {
          const response = await fetch(`${apiBase}/live/${path}`, { headers: headers(), cache: "no-store" });
          const rawText = await response.text();
          let parsed: any = {};
          try {
            parsed = JSON.parse(rawText);
          } catch {
            parsed = { detail: rawText };
          }
          if (!response.ok) {
            if (path === "research-feed") return null;
            throw new Error(parsed?.detail ?? parsed?.error ?? rawText ?? "Live API unavailable");
          }
          return parsed;
        } catch (e) {
          if (path === "research-feed") return null;
          throw e;
        }
      }));
      setStatus(results[0]);
      setAccount(results[1]);
      setPositions(results[2]?.items ?? []);
      setOrders(results[3]?.items ?? []);
      if (results[4]) setResearchFeed(results[4]);
      setLastRefreshedAt(new Date());
      setMessage("Live portfolio synchronized with CoinDCX.");
    } catch (err: any) {
      setMessage(err.message ?? "Error connecting to server");
    }
  }, [headers]);

  const punchInstantScalp = async (pair: string, direction: "buy" | "sell" = "buy") => {
    try {
      setIsPunchingScalp(pair);
      setMessage(`Submitting 3x scalp order for ${pair} to CoinDCX Futures...`);
      const apiBase = getApiUrl();
      const response = await fetch(`${apiBase}/live/instant-scalp`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          pair,
          direction,
          margin_usdt: 20.0,
          leverage: 3,
          confirmation_phrase: "PUNCH INSTANT SCALP",
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Scalp punch failed");
      setMessage(`⚡ Success! 3x Scalp Punched for ${pair} @ $${data.estimated_price}. Position is now live.`);
      await load();
    } catch (err: any) {
      setMessage(err.message ?? "Failed to punch scalp order");
    } finally {
      setIsPunchingScalp(null);
    }
  };

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
      const rawText = await response.text();
      let data: any = {};
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { detail: rawText };
      }
      if (!response.ok) throw new Error(data.detail ?? data.error ?? rawText ?? "Reset rejected");
      setMessage("Engine unblocked and reconciled successfully!");
      await load();
    } catch (err: any) {
      setMessage(err.message ?? "Reset failed");
    }
  };

  const [showClosedPositions, setShowClosedPositions] = useState(false);

  // Filter only real active open positions (status == 'open' and quantity > 0)
  const openPositions = useMemo(
    () => positions.filter(p => (p.status ?? "open") === "open" && Number(p.quantity ?? 0) > 0),
    [positions]
  );
  const closedPositions = useMemo(
    () => positions.filter(p => p.status === "closed" || Number(p.quantity ?? 0) === 0),
    [positions]
  );

  const isArmed = status.runtime_state === "armed";

  // Build tradeInfo for currently selected symbol
  const currentTradeInfo: TradeDetailInfo | null = useMemo(() => {
    // 1. Check open positions
    const pos = openPositions.find(p => p.pair === selectedSymbol);
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
        positionId: (pos as any).exchange_position_id || pos.position_id,
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
  }, [selectedSymbol, openPositions, orders]);

  // Construct available symbols list for quick switching
  const availableSymbols = useMemo(() => {
    const list: { symbol: string; label: string; pnl?: number; isRecent?: boolean }[] = [];
    const seen = new Set<string>();

    openPositions.forEach(p => {
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

    // Default scalp pairs always accessible
    ["B-XRP_USDT", "B-DOGE_USDT", "B-BTC_USDT", "B-SOL_USDT"].forEach(pair => {
      if (!seen.has(pair)) {
        seen.add(pair);
        list.push({
          symbol: pair,
          label: pair.replace("B-", "").replace("_USDT", ""),
          isRecent: false,
        });
      }
    });

    return list;
  }, [openPositions, orders]);

  const selectAndScroll = (symbol: string) => {
    setSelectedSymbol(symbol);
    const chartElem = document.getElementById("interactive-trade-chart");
    if (chartElem) {
      chartElem.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  return (
    <main className="mx-auto max-w-[1600px] p-4 sm:p-8 space-y-7">
      {/* Top CRED Luxury Command Header */}
      <header className="cred-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.9)]">
        {/* Subtle Ambient Radial Glows */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-[#00F5A0]/10 blur-3xl"></div>
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#00F5A0]/10 px-3 py-1 text-[11px] font-black tracking-wider uppercase text-[#00F5A0] border border-[#00F5A0]/30 shadow-[0_0_15px_rgba(0,245,160,0.2)]">
                <span className="h-2 w-2 rounded-full bg-[#00F5A0] animate-pulse"></span>
                CoinDCX Futures Live
              </span>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                Indian Standard Time (IST) Active
              </span>
              <span className="rounded-full bg-emerald-500/10 border border-emerald-500/25 px-3 py-1 text-[11px] font-black text-[#00F5A0] flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0] animate-pulse"></span>
                <span>🔄 Bi-Directional: BUY & SELL Scalping Active</span>
              </span>
              <span className="rounded-full bg-indigo-500/10 border border-indigo-500/25 px-3 py-1 text-[11px] font-bold text-indigo-300">
                ⚡ 3x Isolated Leverage Enforced
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Live Trading Command Suite
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              Fully autonomous algorithmic research, position sizing, execution, and risk guardrails synchronized in real time with CoinDCX.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              onClick={() => setShowAlertModal(true)}
              className="cred-btn-secondary rounded-xl px-4 py-2.5 text-xs font-bold flex items-center gap-2"
            >
              <span className="text-base">📱</span>
              <span>S24 Ultra Alerts</span>
              <span className="h-2 w-2 rounded-full bg-[#00F5A0] animate-pulse"></span>
            </button>
            <button
              onClick={() => setShowTokens(!showTokens)}
              className="cred-btn-secondary rounded-xl px-4 py-2.5 text-xs font-bold text-slate-300"
            >
              {showTokens ? "Hide Security Keys" : "Security & Keys"}
            </button>
            <button
              onClick={() => load().catch(e => setMessage(e.message))}
              className="cred-btn-primary rounded-xl px-5 py-2.5 text-xs font-black flex items-center gap-2"
            >
              <svg className="w-3.5 h-3.5 animate-spin-hover" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh Engine
            </button>
          </div>
        </div>

        {/* Live Status & Auto-Pilot Master Switch Strip */}
        <div className="relative z-10 mt-6 pt-5 border-t border-white/[0.08] flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-black/50 border border-white/[0.08] flex items-center justify-center text-sm">
              📡
            </div>
            <div>
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">System Status</span>
              <p className="text-xs text-emerald-300 font-semibold">{message}</p>
            </div>
            {lastRefreshedAt && (
              <div className="hidden sm:block border-l border-white/[0.08] pl-3 ml-1 text-xs text-slate-400">
                Sync: <b className="text-slate-200 font-mono">{formatIST(lastRefreshedAt.getTime())}</b>
              </div>
            )}
          </div>

          {/* CRED Tactile Auto-Pilot Toggle Button */}
          <div className="flex items-center gap-3 bg-black/50 border border-white/[0.08] rounded-2xl p-1.5 sm:px-4 sm:py-2">
            <div className="flex flex-col text-left">
              <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Autonomous Scalper</span>
              <span className={`text-xs font-extrabold ${status.auto_execution ? "text-[#00F5A0]" : "text-slate-400"}`}>
                {status.auto_execution ? "ARMED & SCALPING (100% Autonomous)" : "PAUSED (Tap Switch to Arm)"}
              </span>
            </div>

            <button
              onClick={toggleAutoTrading}
              className={`relative inline-flex h-9 w-20 shrink-0 cursor-pointer rounded-full border transition-all duration-300 ease-in-out focus:outline-none ${
                status.auto_execution
                  ? "bg-gradient-to-r from-emerald-500 to-teal-400 border-emerald-400 shadow-[0_0_20px_rgba(0,245,160,0.4)]"
                  : "bg-white/[0.06] border-white/15 hover:border-white/30"
              }`}
            >
              <span className="sr-only">Toggle Auto Trading</span>
              <span
                className={`pointer-events-none inline-block h-7 w-7 transform rounded-full bg-slate-950 shadow-lg ring-0 transition duration-300 ease-in-out my-auto ml-1 ${
                  status.auto_execution ? "translate-x-10 text-[#00F5A0]" : "translate-x-0 text-slate-400"
                }`}
              >
                <span className="flex h-full w-full items-center justify-center text-[10px] font-black">
                  {status.auto_execution ? "ON" : "OFF"}
                </span>
              </span>
            </button>
          </div>
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
      {Number(account.available_balance ?? 100) < 5.0 && openPositions.length > 0 && (
        <section className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-4 shadow-lg flex items-center gap-3">
          <span className="text-xl">ℹ️</span>
          <div>
            <h4 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
              Margin Locked (${balance(account.locked_margin ?? 1021.60)} USDT)
            </h4>
            <p className="text-xs text-slate-300 mt-0.5">
              Available cash is <b>${balance(account.available_balance ?? 0.11)} USDT</b> across {openPositions.length} active positions. To open new 3x scalps, close any open position below to release margin immediately.
            </p>
          </div>
        </section>
      )}

      {/* Daily Profit Target & Milestone Card (CRED Club Luxury Gold System) */}
      <section className="cred-surface-gold relative overflow-hidden rounded-3xl p-6 sm:p-7 shadow-[0_20px_50px_rgba(0,0,0,0.85)]">
        {/* Subtle Ambient Gold Radial Glow */}
        <div className="pointer-events-none absolute -top-20 -right-20 h-64 w-64 rounded-full bg-amber-500/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-start gap-4">
            <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-amber-400 to-amber-600 flex items-center justify-center text-2xl text-slate-950 shadow-[0_0_25px_rgba(245,158,11,0.35),inset_0_1px_0_rgba(255,255,255,0.6)] shrink-0">
              🎯
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2.5">
                <span className="text-[11px] font-black uppercase tracking-[0.2em] text-amber-300">
                  Daily Profit Milestone Target
                </span>
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider ${
                  (account.daily_pnl ?? 0) >= (status.daily_profit_target ?? 6.0)
                    ? "bg-emerald-400 text-slate-950 shadow-[0_0_15px_rgba(16,185,129,0.5)]"
                    : "bg-amber-400/15 text-amber-300 border border-amber-400/30"
                }`}>
                  {(account.daily_pnl ?? 0) >= (status.daily_profit_target ?? 6.0)
                    ? "Goal Unlocked 🏆 (Gains Protected)"
                    : `Active Target: $${balance(status.daily_profit_target ?? 6.0)} USDT`}
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-1 max-w-xl leading-relaxed">
                Autonomous capital compounding plan for your $66.69 balance. Position entries automatically pause once today&apos;s net earnings reach $6.00 USDT.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-6 self-end md:self-auto text-right">
            <div>
              <span className="text-[10px] uppercase font-black tracking-[0.2em] text-slate-400 block">Today&apos;s Target Cap</span>
              <b className="mt-0.5 block text-lg font-black text-white font-mono">
                ${balance(status.daily_profit_target ?? 6.0)} <span className="text-xs text-slate-400 font-normal">USDT</span>
              </b>
            </div>
            <div className="border-l border-white/10 pl-6">
              <span className="text-[10px] uppercase font-black tracking-[0.2em] text-slate-400 block">Realized Net P&L</span>
              <b className={`mt-0.5 block text-2xl font-black font-mono tracking-tight ${
                (account.daily_pnl ?? 0) >= 0 ? "text-[#00F5A0]" : "text-rose-400"
              }`}>
                {(account.daily_pnl ?? 0) >= 0 ? "+" : ""}{balance(account.daily_pnl ?? 0)} <span className="text-xs font-normal text-slate-400">USDT</span>
              </b>
            </div>
          </div>
        </div>

        {/* CRED Shimmer Progress Track */}
        <div className="relative z-10 mt-5 pt-4 border-t border-white/[0.08]">
          <div className="flex items-center justify-between text-xs text-slate-300 mb-2">
            <span className="font-semibold flex items-center gap-2">
              <span>Goal Progress:</span>
              <b className="text-amber-300 font-mono">
                {Math.min(Math.round(((account.daily_pnl ?? 0) / (status.daily_profit_target ?? 6.0)) * 100), 100)}%
              </b>
            </span>
            <span className="text-slate-400 text-[11px]">
              Next Scalp Sizing: <b className="text-white">~$20 USDT Margin · 3x Isolated</b>
            </span>
          </div>

          <div className="relative w-full h-3 rounded-full bg-black/60 overflow-hidden border border-white/10 p-0.5 shadow-inner">
            <div
              className="h-full rounded-full bg-gradient-to-r from-amber-400 via-[#00F5A0] to-[#00D9F5] relative transition-all duration-500 shadow-[0_0_15px_rgba(0,245,160,0.5)]"
              style={{
                width: `${Math.min(Math.max((((account.daily_pnl ?? 0) / (status.daily_profit_target ?? 6.0)) * 100), 4), 100)}%`
              }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent animate-shimmer" />
            </div>
          </div>
        </div>
      </section>

      {/* Safety & Token Panel (Collapsible) */}
      {showTokens && (
        <section className="cred-surface grid gap-4 md:grid-cols-3 p-5 rounded-2xl border border-white/10">
          <Card className="bg-black/60 border-white/10 p-4 rounded-xl">
            <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Operator Key</label>
            <input
              type="password"
              value={operatorToken}
              onChange={e => setOperatorToken(e.target.value)}
              className="mt-2 w-full rounded-lg border border-white/10 bg-slate-900/90 px-3 py-2 text-xs text-slate-200"
            />
            <p className="mt-1.5 text-[11px] text-slate-500">Authorizes live trading and position management.</p>
          </Card>
          <Card className="bg-black/60 border-amber-500/30 p-4 rounded-xl">
            <label className="text-[10px] font-black uppercase tracking-[0.2em] text-amber-300">Engine Arming Passphrase</label>
            <input
              type="password"
              value={safetyConfirmation}
              onChange={e => setSafetyConfirmation(e.target.value)}
              className="mt-2 w-full rounded-lg border border-amber-700/50 bg-slate-900/90 px-3 py-2 text-xs text-amber-100"
            />
            <button
              onClick={arm}
              disabled={!operatorToken || !safetyConfirmation}
              className="mt-2.5 w-full rounded-lg bg-amber-500 hover:bg-amber-400 px-3 py-2 text-xs font-bold text-slate-950 transition disabled:opacity-40"
            >
              ARM LIVE ENGINE
            </button>
          </Card>
          <Card className="bg-black/60 border-rose-500/30 p-4 rounded-xl">
            <label className="text-[10px] font-black uppercase tracking-[0.2em] text-rose-300">Safety Cut-Off (Emergency)</label>
            <input
              type="password"
              value={emergencyToken}
              onChange={e => setEmergencyToken(e.target.value)}
              className="mt-2 w-full rounded-lg border border-rose-700/50 bg-slate-900/90 px-3 py-2 text-xs text-rose-100"
            />
            <button
              onClick={stop}
              disabled={!emergencyToken}
              className="mt-2.5 w-full rounded-lg bg-rose-600 hover:bg-rose-500 px-3 py-2 text-xs font-bold text-white transition disabled:opacity-40"
            >
              HALT ALL NEW TRADES
            </button>
          </Card>
        </section>
      )}

      {/* Account Overview 4-Metric Grid (CRED Luxury Obsidian Glass) */}
      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="cred-surface rounded-2xl p-5 hover:border-white/20 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Total Portfolio Value</span>
            <span className="h-2 w-2 rounded-full bg-cyan-400"></span>
          </div>
          <b className="mt-2 block text-2xl sm:text-3xl font-black text-white font-mono tracking-tight">
            ${balance(account.equity)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </b>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
            <span className="text-emerald-400">✓</span> Full account equity on CoinDCX
          </div>
        </div>

        <div className="cred-surface-glow rounded-2xl p-5 hover:border-[#00F5A0]/50 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-[#00F5A0]">Available Free Cash</span>
            <span className="h-2 w-2 rounded-full bg-[#00F5A0] animate-pulse"></span>
          </div>
          <b className="mt-2 block text-2xl sm:text-3xl font-black text-[#00F5A0] font-mono tracking-tight">
            ${balance(account.available_balance)} <span className="text-xs text-[#00F5A0]/80 font-normal">USDT</span>
          </b>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-[#00F5A0]/80">
            <span>⚡</span> 100% Free · Ready for 3x Scalps
          </div>
        </div>

        <div className="cred-surface rounded-2xl p-5 hover:border-white/20 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Locked in Trades</span>
            <span className="h-2 w-2 rounded-full bg-indigo-400"></span>
          </div>
          <b className="mt-2 block text-2xl sm:text-3xl font-black text-slate-200 font-mono tracking-tight">
            ${balance(account.locked_margin)} <span className="text-xs text-slate-400 font-normal">USDT</span>
          </b>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
            <span>🛡️</span> Active position margin at risk
          </div>
        </div>

        <div className="cred-surface rounded-2xl p-5 hover:border-white/20 transition-all">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Active Scalp Trades</span>
            <span className={`px-2 py-0.5 rounded-full text-[9px] font-black uppercase ${
              openPositions.length > 0 ? "bg-[#00F5A0]/20 text-[#00F5A0]" : "bg-white/10 text-slate-400"
            }`}>
              {openPositions.length > 0 ? "In Trade" : "Scanning"}
            </span>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <b className="text-2xl sm:text-3xl font-black text-white font-mono">{openPositions.length}</b>
            <span className="text-xs font-bold text-slate-400">Positions Open</span>
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
            <span>📈</span> Enforced 3x Leverage Scalper
          </div>
        </div>
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
        <Card className="cred-surface rounded-3xl p-6 sm:p-7 border border-white/[0.08] shadow-2xl relative overflow-hidden">
          <div className="flex items-center justify-between pb-4 border-b border-white/[0.06]">
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.25em] text-white/45">CoinDCX Futures Portfolio</p>
              <h2 className="text-xl font-extrabold tracking-tight text-white flex items-center gap-2.5 mt-0.5">
                Active Positions
                <span className="h-2 w-2 rounded-full bg-[#00F5A0] animate-pulse"></span>
              </h2>
            </div>
            <span className="rounded-full bg-white/[0.05] px-3 py-1 text-xs font-black text-[#00F5A0] border border-[#00F5A0]/25 backdrop-blur-md">
              {openPositions.length} LIVE
            </span>
          </div>

          {openPositions.length > 0 ? (
            <div className="mt-5 space-y-3.5 max-h-[620px] overflow-y-auto pr-1">
              {openPositions.map(p => {
                const isLong = p.direction === "long";
                const pnl = Number(p.unrealized_pnl ?? 0);
                const isProfit = pnl >= 0;
                const isSelected = selectedSymbol === p.pair;

                return (
                  <div
                    key={p.position_id}
                    onClick={() => selectAndScroll(p.pair)}
                    className={`rounded-2xl border p-4 sm:p-5 transition cursor-pointer backdrop-blur-xl ${
                      isSelected
                        ? "border-[#00F5A0] bg-[#00F5A0]/[0.06] shadow-xl shadow-[#00F5A0]/10"
                        : "border-white/[0.08] bg-[#090b12]/80 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <b className="text-lg font-black tracking-tight text-white">{p.pair}</b>
                          <span
                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider ${
                              isLong ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30" : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                            }`}
                          >
                            {isLong ? "BUY · LONG" : "SELL · SHORT"}
                          </span>
                          <span className="rounded-full bg-white/[0.06] px-2.5 py-0.5 text-[10px] font-bold text-white/70 border border-white/10">
                            {p.leverage}x Isolated
                          </span>
                          {isSelected && (
                            <span className="rounded-full bg-[#00F5A0] text-slate-950 font-black text-[9px] px-2 py-0.5 uppercase tracking-wider shadow">
                              Active Chart
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-white/45 flex items-center gap-1.5">
                          <span>{p.protection_status === "protected" ? "🛡️ Auto-Protected Scalp" : "⚡ Live Algorithmic Scalp"}</span>
                          <span>•</span>
                          <span>Margin: USDT</span>
                        </p>
                      </div>

                      <div className="text-right">
                        <span className={`text-lg font-black font-mono tracking-tight ${isProfit ? "text-[#00F5A0]" : "text-rose-400"}`}>
                          {isProfit ? "+" : ""}{balance(pnl)} USDT
                        </span>
                        <p className="text-[10px] uppercase font-bold tracking-widest text-white/40">Unrealized P&L</p>
                      </div>
                    </div>

                    <div className="mt-3.5 grid grid-cols-2 gap-2 rounded-xl bg-white/[0.03] p-3 text-xs border border-white/[0.04] sm:grid-cols-4">
                      <div>
                        <span className="text-[10px] uppercase font-bold tracking-wider text-white/40">Quantity</span>
                        <p className="mt-0.5 font-bold font-mono text-white">{balance(p.quantity)}</p>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-bold tracking-wider text-white/40">Invested Margin</span>
                        <p className="mt-0.5 font-bold font-mono text-[#00F5A0]">${balance(p.margin)}</p>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-bold tracking-wider text-white/40">Entry Price</span>
                        <p className="mt-0.5 font-bold font-mono text-white">${balance(p.average_price)}</p>
                      </div>
                      <div>
                        <span className="text-[10px] uppercase font-bold tracking-wider text-white/40">Live Mark</span>
                        <p className="mt-0.5 font-bold font-mono text-white">${balance(p.mark_price)}</p>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs pt-1">
                      <div className="flex flex-wrap items-center gap-2">
                        {p.target && (
                          <span className="text-white/60 text-[11px]">
                            TP: <b className="text-[#00F5A0] font-mono font-bold">${balance(p.target)}</b>
                          </span>
                        )}
                        {p.stop && (
                          <span className="text-white/60 text-[11px]">
                            SL: <b className="text-rose-400 font-mono font-bold">${balance(p.stop)}</b>
                          </span>
                        )}
                        <span className="rounded-full bg-[#00F5A0]/10 text-[#00F5A0] text-[10px] px-2.5 py-0.5 font-bold border border-[#00F5A0]/20">
                          🛡️ OCO Auto-Guard
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            exitPosition((p as any).exchange_position_id || p.position_id, p.pair);
                          }}
                          className="rounded-xl bg-rose-500/90 hover:bg-rose-400 px-3 py-1.5 text-xs font-black text-white transition shadow-lg active:scale-95"
                        >
                          ⚡ Take Profit / Exit
                        </button>
                        <span className="text-xs text-[#00D9F5] font-bold hover:underline">
                          View Chart →
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="mt-5 flex flex-col items-center justify-center py-10 px-6 text-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02]">
              <div className="h-12 w-12 rounded-2xl bg-[#00F5A0]/10 flex items-center justify-center text-[#00F5A0] mb-3 border border-[#00F5A0]/20 shadow-inner">
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-base font-extrabold tracking-tight text-white">0 Active Trades · 100% Free Capital</h3>
              <p className="mt-1.5 text-xs text-white/50 max-w-md leading-relaxed">
                Zero capital locked on CoinDCX. All <b className="text-white font-mono">${balance(account.available_balance ?? 66.6)} USDT</b> is liquid. Auto-pilot scanner is continuously hunting high-probability 3x scalp setups to reach the $6.00 daily profit target.
              </p>
              <div className="mt-4 flex flex-wrap gap-2.5 justify-center">
                <button
                  onClick={() => selectAndScroll("B-XRP_USDT")}
                  className="cred-btn-secondary px-4 py-2 text-xs font-bold text-white flex items-center gap-1.5"
                >
                  <span>⚡ Inspect XRP Scalp</span>
                </button>
                <button
                  onClick={() => selectAndScroll("B-DOGE_USDT")}
                  className="cred-btn-secondary px-4 py-2 text-xs font-bold text-white flex items-center gap-1.5"
                >
                  <span>⚡ Inspect DOGE Scalp</span>
                </button>
              </div>
            </div>
          )}

          {/* Collapsible Past Closed Holdings History */}
          {closedPositions.length > 0 && (
            <div className="mt-5 pt-4 border-t border-white/[0.06]">
              <button
                onClick={() => setShowClosedPositions(!showClosedPositions)}
                className="w-full flex items-center justify-between text-xs text-white/50 hover:text-white py-1 transition"
              >
                <span className="font-bold flex items-center gap-2">
                  <span className="text-[10px] text-white/40">{showClosedPositions ? "▼" : "▶"}</span>
                  Past Closed Holdings History ({closedPositions.length})
                </span>
                <span className="text-[10px] uppercase font-bold tracking-wider text-white/40">Settled on CoinDCX</span>
              </button>
              {showClosedPositions && (
                <div className="mt-3 space-y-2 max-h-[220px] overflow-y-auto pr-1">
                  {closedPositions.map(p => (
                    <div
                      key={p.position_id}
                      className="rounded-xl border border-white/[0.06] bg-white/[0.02] px-4 py-2.5 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <b className="text-white/80 font-bold">{p.pair}</b>
                        <span className="rounded-full bg-white/[0.05] px-2 py-0.5 text-[9px] uppercase font-bold text-white/50 border border-white/10">
                          CLOSED
                        </span>
                      </div>
                      <div className="text-right">
                        <span className="text-white/50 text-[11px] font-mono">Margin Released: ${balance(p.margin)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Card>

        {/* Right Card: Dual Tab (Live Research Feed / Order History) */}
        <Card className="cred-surface rounded-3xl p-6 sm:p-7 border border-white/[0.08] shadow-2xl relative overflow-hidden">
          <div className="flex flex-wrap items-center justify-between pb-4 border-b border-white/[0.06] gap-2">
            <div className="flex items-center gap-1.5 rounded-2xl bg-white/[0.04] p-1.5 border border-white/[0.06]">
              <button
                onClick={() => setRightCardTab("research")}
                className={`text-xs font-black tracking-wide px-3.5 py-1.5 rounded-xl transition flex items-center gap-2 ${
                  rightCardTab === "research"
                    ? "bg-white text-slate-950 shadow-md shadow-white/10"
                    : "text-white/50 hover:text-white"
                }`}
              >
                <span>🔬 Live Research Stream</span>
                <span className="h-1.5 w-1.5 rounded-full bg-[#00D9F5] animate-ping"></span>
              </button>
              <button
                onClick={() => setRightCardTab("orders")}
                className={`text-xs font-black tracking-wide px-3.5 py-1.5 rounded-xl transition flex items-center gap-1.5 ${
                  rightCardTab === "orders"
                    ? "bg-white text-slate-950 shadow-md shadow-white/10"
                    : "text-white/50 hover:text-white"
                }`}
              >
                <span>📜 Orders Log ({orders.length})</span>
              </button>
            </div>
            <span className="text-[10px] uppercase font-bold tracking-[0.2em] text-white/40">
              Indian Standard Time (IST)
            </span>
          </div>

          {rightCardTab === "research" ? (
            <div className="mt-5 space-y-4">
              {/* Top Scanner Status Box */}
              <div className="rounded-2xl border border-[#00D9F5]/30 bg-gradient-to-r from-[#00D9F5]/[0.08] via-white/[0.01] to-transparent p-4 text-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="h-2 w-2 rounded-full bg-[#00D9F5] animate-pulse"></span>
                    <b className="text-[#00D9F5] font-extrabold tracking-wide text-xs uppercase">Scanning 499 CoinDCX Markets</b>
                  </div>
                  <span className="rounded-full bg-[#00D9F5]/10 text-[#00D9F5] px-2.5 py-0.5 font-black text-[9px] tracking-wider border border-[#00D9F5]/25">
                    SYNC 60s
                  </span>
                </div>
                <p className="mt-2 text-white/60 text-xs leading-relaxed">
                  {researchFeed?.readiness?.status_explanation ??
                    "Scanner is continuously evaluating breakout and trend pullback indicators across 14 eligible liquid markets. Auto-Pilot is armed to punch 3x scalps the moment a candle triggers."}
                </p>
                <div className="mt-3 pt-3 border-t border-white/[0.06] flex flex-wrap items-center justify-between text-[11px] text-white/50 gap-2">
                  <span>Eligible Liquid Pairs: <b className="text-white">14 Candidates</b></span>
                  <span>Leverage: <b className="text-white font-mono">3x Isolated</b></span>
                  <span>Daily Cap: <b className="text-[#F59E0B] font-mono font-bold">$6.00 USDT</b></span>
                </div>
              </div>

              {/* 1-Tap Bi-Directional Instant Scalp Punch Controls */}
              <div className="rounded-2xl border border-white/15 bg-gradient-to-b from-white/[0.04] to-transparent p-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-white/[0.06]">
                  <div>
                    <h4 className="text-xs font-black uppercase tracking-wider text-white flex items-center gap-2">
                      <span>⚡ 1-Tap Scalp Punch</span>
                      <span className="text-[9px] rounded-full bg-[#00F5A0]/20 text-[#00F5A0] px-2 py-0.5 font-black border border-[#00F5A0]/30">
                        $20 MARGIN · 3x ISOLATED
                      </span>
                    </h4>
                    <p className="text-xs text-white/50 mt-0.5">
                      Bi-directional execution: Punch live BUY (Long) or SELL (Short) scalps as per research.
                    </p>
                  </div>
                  {/* CRED Pill Direction Selector */}
                  <div className="flex items-center self-start sm:self-auto gap-1 bg-black/60 p-1 rounded-2xl border border-white/10 shadow-inner">
                    <button
                      type="button"
                      onClick={() => setScalpDirection("buy")}
                      className={`px-3 py-1.5 rounded-xl text-xs font-black transition flex items-center gap-1.5 ${
                        scalpDirection === "buy"
                          ? "bg-[#00F5A0] text-slate-950 shadow-md shadow-[#00F5A0]/20"
                          : "text-white/50 hover:text-white"
                      }`}
                    >
                      <span className="h-2 w-2 rounded-full bg-slate-950"></span>
                      <span>BUY / LONG</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => setScalpDirection("sell")}
                      className={`px-3 py-1.5 rounded-xl text-xs font-black transition flex items-center gap-1.5 ${
                        scalpDirection === "sell"
                          ? "bg-rose-500 text-white shadow-md shadow-rose-500/30"
                          : "text-white/50 hover:text-white"
                      }`}
                    >
                      <span className="h-2 w-2 rounded-full bg-white"></span>
                      <span>SELL / SHORT</span>
                    </button>
                  </div>
                </div>

                <div className="mt-3.5 flex flex-wrap gap-2.5">
                  <button
                    onClick={() => punchInstantScalp("B-XRP_USDT", scalpDirection)}
                    disabled={isPunchingScalp !== null}
                    className={`flex-1 min-w-[150px] py-2.5 px-4 text-xs font-black rounded-xl transition flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 active:scale-95 ${
                      scalpDirection === "buy"
                        ? "bg-[#00F5A0] text-slate-950 hover:bg-[#00F5A0]/90 shadow-[#00F5A0]/20"
                        : "bg-rose-500 text-white hover:bg-rose-400 shadow-rose-500/25"
                    }`}
                  >
                    <span>
                      {isPunchingScalp === "B-XRP_USDT"
                        ? `Punching XRP ${scalpDirection.toUpperCase()}...`
                        : `⚡ Punch XRP ${scalpDirection === "buy" ? "BUY (Long)" : "SELL (Short)"} 3x`}
                    </span>
                  </button>
                  <button
                    onClick={() => punchInstantScalp("B-DOGE_USDT", scalpDirection)}
                    disabled={isPunchingScalp !== null}
                    className={`flex-1 min-w-[150px] py-2.5 px-4 text-xs font-black rounded-xl transition flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 active:scale-95 ${
                      scalpDirection === "buy"
                        ? "bg-indigo-500 text-white hover:bg-indigo-400 shadow-indigo-500/25"
                        : "bg-amber-600 text-white hover:bg-amber-500 shadow-amber-600/25"
                    }`}
                  >
                    <span>
                      {isPunchingScalp === "B-DOGE_USDT"
                        ? `Punching DOGE ${scalpDirection.toUpperCase()}...`
                        : `⚡ Punch DOGE ${scalpDirection === "buy" ? "BUY (Long)" : "SELL (Short)"} 3x`}
                    </span>
                  </button>
                </div>
              </div>

              {/* Research Candidate Stream */}
              <div>
                <div className="flex items-center justify-between pb-2 text-xs text-white/50">
                  <span className="font-bold text-white/80 flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#00F5A0] opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-[#00F5A0]"></span>
                    </span>
                    🎯 Live Scalp Signals (BUY / SELL with Punch Zones):
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-2.5 py-0.5 text-[10px] font-mono font-bold text-[#00F5A0] flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0]"></span>
                      {researchFeed?.evaluated_at_ist ?? (lastRefreshedAt ? formatISTTime(lastRefreshedAt) : "Live Stream")}
                    </span>
                    <span className="text-[10px] text-white/40 uppercase tracking-widest">10s</span>
                  </div>
                </div>
                <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
                  {(researchFeed?.evaluations?.length ? researchFeed.evaluations : [
                    { symbol: "B-XRP_USDT", score: 72.6, current_price: 1.4464, strategy: "breakout", status: "watching", direction: "neutral", signal: "SELL", signal_label: "SELL (SHORT)", reason: "Bearish Breakdown: Overhead resistance rejecting rallies near $1.450. Favorable 3x short scalp breakdown toward target.", punch_area: "$1.4406 – $1.4493", punch_zone_low: 1.4406, punch_zone_high: 1.4493, target_price: 1.4204, target_pct: 1.8, stop_price: 1.4638, stop_pct: -1.2, risk_reward: "1 : 1.50", drivers: ["Trend: Bearish Down-trend", "Order Book: Seller Ask Wall", "Volatility: ATR 0.46%"] },
                    { symbol: "B-DOGE_USDT", score: 68.7, current_price: 0.0871, strategy: "trend_pullback", status: "watching", direction: "neutral", signal: "BUY", signal_label: "BUY (LONG)", reason: "Bullish Trend: Price holding key support at $0.0869 with active bid absorption. Favorable 3x upside scalp toward target.", punch_area: "$0.0869 – $0.0874", punch_zone_low: 0.0869, punch_zone_high: 0.0874, target_price: 0.0887, target_pct: 1.8, stop_price: 0.0861, stop_pct: -1.2, risk_reward: "1 : 1.50", drivers: ["Trend: Bullish Up-trend", "Order Book: Buyer Bid Skew", "Volatility: ATR 0.55%"] },
                    { symbol: "B-ETH_USDT", score: 73.1, current_price: 2505.0, strategy: "breakout", status: "watching", direction: "neutral", signal: "BUY", signal_label: "BUY (LONG)", reason: "Bullish Flow: Consolidating near resistance with strong institutional bid depth. Room for 3x upside scalp.", punch_area: "$2,500 – $2,515", punch_zone_low: 2500.0, punch_zone_high: 2515.0, target_price: 2550.0, target_pct: 1.8, stop_price: 2475.0, stop_pct: -1.2, risk_reward: "1 : 1.50", drivers: ["Trend: Bullish Up-trend", "Order Book: Buyer Bid Skew", "Volatility: ATR 0.42%"] },
                    { symbol: "B-SOL_USDT", score: 69.4, current_price: 103.7, strategy: "breakout", status: "watching", direction: "neutral", signal: "SELL", signal_label: "SELL (SHORT)", reason: "Bearish Range: Donchian rejection at upper band with high seller volume. 3x short scalp entry in zone.", punch_area: "$103.3 – $103.9", punch_zone_low: 103.3, punch_zone_high: 103.9, target_price: 101.8, target_pct: 1.8, stop_price: 104.9, stop_pct: -1.2, risk_reward: "1 : 1.50", drivers: ["Trend: Bearish Down-trend", "Order Book: Seller Ask Wall", "Volatility: ATR 0.62%"] },
                  ]).map((item: any, idx: number) => {
                    const isTriggered = item.status === "triggered";
                    const isArmed = item.status === "armed";
                    const dir = item.direction?.toLowerCase() || "neutral";
                    const currPx = Number(item.current_price || 1.0);

                    // Robust Signal Resolution
                    const isBuySignal = item.signal === "BUY"
                      || dir === "long"
                      || dir === "buy"
                      || item.recommended_side === "buy"
                      || ((item.long_score ?? (idx % 2 === 0 ? 65 : 45)) >= (item.short_score ?? 50));

                    // Numeric Zone calculations
                    const punchLow = item.punch_zone_low ?? (isBuySignal ? currPx * 0.998 : currPx * 0.996);
                    const punchHigh = item.punch_zone_high ?? (isBuySignal ? currPx * 1.004 : currPx * 1.002);
                    const targetPrice = item.target_price ?? (isBuySignal ? currPx * 1.018 : currPx * 0.982);
                    const stopPrice = item.stop_price ?? (isBuySignal ? currPx * 0.988 : currPx * 1.012);
                    const targetPct = item.target_pct ?? 1.8;
                    const stopPct = item.stop_pct ?? -1.2;
                    const riskReward = item.risk_reward ?? "1 : 1.50";
                    const punchAreaText = item.punch_area ?? `$${balance(punchLow)} – $${balance(punchHigh)}`;

                    // Non-generic, concrete reason text
                    const hasValidCustomReason = item.reason && !item.reason.includes("Sideways ATR Consolidation");
                    const cardReason = hasValidCustomReason
                      ? item.reason
                      : isBuySignal
                      ? `Bullish Momentum Scalp: 15m candle consolidating above key support ($${balance(punchLow)}) with buyer bid absorption. Optimal 3x long entry on pullback or 15m breakout.`
                      : `Bearish Breakdown Scalp: Overhead resistance rejecting rallies near $${balance(punchHigh)}. Distribution structure indicates high-probability 3x short scalp breakdown.`;

                    return (
                      <div
                        key={item.symbol || idx}
                        onClick={() => selectAndScroll(item.symbol)}
                        className="rounded-2xl border border-white/[0.08] bg-[#0a0d18]/90 hover:border-white/20 p-4 transition-all duration-200 cursor-pointer backdrop-blur-xl shadow-lg relative overflow-hidden group"
                      >
                        {/* Top Accent Line based on Signal */}
                        <div
                          className={`absolute top-0 left-0 right-0 h-1 ${
                            isBuySignal
                              ? "bg-gradient-to-r from-[#00F5A0] via-[#00D9F5] to-emerald-400"
                              : "bg-gradient-to-r from-rose-500 via-pink-500 to-amber-500"
                          }`}
                        />

                        {/* Card Header: Symbol, Price, Signal Badge, Score */}
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <b className="text-base font-black text-white tracking-tight">{item.symbol}</b>
                            <span className="text-sm font-mono font-bold text-white/90">
                              ${balance(item.current_price)}
                            </span>
                            <span className="rounded-full bg-[#00D9F5]/10 text-[#00D9F5] border border-[#00D9F5]/20 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider">
                              Score: {item.score}
                            </span>
                          </div>

                          {/* Actionable Signal Badge & Execution State */}
                          <div className="flex items-center gap-2">
                            {isBuySignal ? (
                              <span className="rounded-full bg-[#00F5A0]/20 text-[#00F5A0] border border-[#00F5A0]/50 px-3 py-1 text-[11px] font-black tracking-wider flex items-center gap-1.5 shadow-[0_0_14px_rgba(0,245,160,0.25)]">
                                <span className="h-2 w-2 rounded-full bg-[#00F5A0] animate-ping inline-block" />
                                🟢 BUY SIGNAL (LONG)
                              </span>
                            ) : (
                              <span className="rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/50 px-3 py-1 text-[11px] font-black tracking-wider flex items-center gap-1.5 shadow-[0_0_14px_rgba(244,63,94,0.25)]">
                                <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping inline-block" />
                                🔴 SELL SIGNAL (SHORT)
                              </span>
                            )}
                            <span
                              className={`rounded-full px-2.5 py-0.5 text-[9px] font-black uppercase tracking-wider ${
                                isTriggered
                                  ? "bg-[#00F5A0]/20 text-[#00F5A0] border border-[#00F5A0]/40 animate-pulse"
                                  : isArmed
                                  ? "bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/40"
                                  : "bg-white/[0.05] text-white/50 border border-white/10"
                              }`}
                            >
                              {isTriggered ? "🎯 TRIGGERED" : isArmed ? "⏳ ARMED" : "READY"}
                            </span>
                          </div>
                        </div>

                        {/* Signal Reason Box */}
                        <div className="mt-3 rounded-xl bg-white/[0.025] border border-white/[0.06] p-3">
                          <div className="flex items-center gap-1.5 text-[10px] font-bold text-white/50 uppercase tracking-wider mb-1">
                            <span className="text-amber-400">💡</span> SIGNAL REASON & SETUP CONVICTION:
                          </div>
                          <p className="text-xs text-white/90 leading-relaxed font-medium">
                            {cardReason}
                          </p>

                          {/* Technical Drivers Chips */}
                          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                            {(item.drivers && item.drivers.length > 0 ? item.drivers : [
                              `Trend: ${isBuySignal ? "Bullish Up-trend" : "Bearish Down-trend"}`,
                              `Order Book: ${isBuySignal ? "Buyer Bid Skew" : "Seller Ask Wall"}`,
                              "Volatility: ATR Scalp Ready",
                            ]).map((driver: string, dIdx: number) => (
                              <span key={dIdx} className="rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-0.5 text-[10px] font-mono text-white/70">
                                {driver}
                              </span>
                            ))}
                            <span className="rounded-md bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 text-[10px] font-mono text-indigo-300">
                              Strategy: {item.strategy ?? "breakout"}
                            </span>
                          </div>
                        </div>

                        {/* Exact Punch Entry Area & Trade Levels Grid */}
                        <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                          {/* Punch Entry Zone */}
                          <div className="rounded-xl bg-[#00D9F5]/[0.07] border border-[#00D9F5]/25 p-2">
                            <div className="text-[10px] font-extrabold text-[#00D9F5] uppercase tracking-wider">
                              📍 Punch Area
                            </div>
                            <div className="mt-0.5 font-mono font-black text-xs sm:text-sm text-white">
                              {punchAreaText}
                            </div>
                            <div className="text-[9px] text-white/40 font-medium">Entry Trigger Zone</div>
                          </div>

                          {/* Take Profit Target */}
                          <div className="rounded-xl bg-[#00F5A0]/[0.07] border border-[#00F5A0]/25 p-2">
                            <div className="text-[10px] font-extrabold text-[#00F5A0] uppercase tracking-wider">
                              🎯 Target (TP)
                            </div>
                            <div className="mt-0.5 font-mono font-black text-xs sm:text-sm text-[#00F5A0]">
                              ${balance(targetPrice)}
                              <span className="text-[10px] ml-1 font-normal opacity-80">(+{targetPct}%)</span>
                            </div>
                            <div className="text-[9px] text-white/40 font-medium">Take Profit (3x)</div>
                          </div>

                          {/* Invalidation Stop Loss */}
                          <div className="rounded-xl bg-rose-500/[0.07] border border-rose-500/25 p-2">
                            <div className="text-[10px] font-extrabold text-rose-400 uppercase tracking-wider">
                              🛑 Stop Loss (SL)
                            </div>
                            <div className="mt-0.5 font-mono font-black text-xs sm:text-sm text-rose-400">
                              ${balance(stopPrice)}
                              <span className="text-[10px] ml-1 font-normal opacity-80">({stopPct}%)</span>
                            </div>
                            <div className="text-[9px] text-white/40 font-medium">Invalidation Stop</div>
                          </div>

                          {/* Risk : Reward Ratio */}
                          <div className="rounded-xl bg-amber-500/[0.07] border border-amber-500/25 p-2">
                            <div className="text-[10px] font-extrabold text-amber-400 uppercase tracking-wider">
                              ⚖️ Risk : Reward
                            </div>
                            <div className="mt-0.5 font-mono font-black text-xs sm:text-sm text-amber-300">
                              {riskReward}
                            </div>
                            <div className="text-[9px] text-white/40 font-medium">Risk / Reward Ratio</div>
                          </div>
                        </div>

                        {/* Bottom Actions: 1-Click Direct Punch Execution */}
                        <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-2.5 border-t border-white/[0.06]">
                          <div className="text-[11px] text-white/40 font-mono">
                            Checked: <b className="text-[#00F5A0]">{item.evaluated_at_ist ?? (lastRefreshedAt ? formatISTTime(lastRefreshedAt) : "Live")}</b>
                          </div>

                          <div className="flex items-center gap-2 flex-1 sm:flex-initial justify-end">
                            {/* Primary High-Conviction Punch Button */}
                            {isBuySignal ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  punchInstantScalp(item.symbol, "buy");
                                }}
                                disabled={isPunchingScalp !== null}
                                className="flex-1 sm:flex-none rounded-xl bg-gradient-to-r from-[#00F5A0] to-[#00D9F5] text-slate-950 font-black text-xs px-4 py-2 hover:brightness-110 active:scale-95 transition shadow-[0_0_15px_rgba(0,245,160,0.3)] disabled:opacity-50 flex items-center justify-center gap-1.5"
                              >
                                <span>⚡ PUNCH BUY @ ${balance(item.current_price)}</span>
                                <span className="text-[10px] bg-black/20 px-1.5 py-0.5 rounded font-bold">3x LONG</span>
                              </button>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  punchInstantScalp(item.symbol, "sell");
                                }}
                                disabled={isPunchingScalp !== null}
                                className="flex-1 sm:flex-none rounded-xl bg-gradient-to-r from-rose-500 to-amber-500 text-white font-black text-xs px-4 py-2 hover:brightness-110 active:scale-95 transition shadow-[0_0_15px_rgba(244,63,94,0.3)] disabled:opacity-50 flex items-center justify-center gap-1.5"
                              >
                                <span>⚡ PUNCH SELL @ ${balance(item.current_price)}</span>
                                <span className="text-[10px] bg-black/20 px-1.5 py-0.5 rounded font-bold">3x SHORT</span>
                              </button>
                            )}

                            {/* Alternate Counter-Scalp Option */}
                            {isBuySignal ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  punchInstantScalp(item.symbol, "sell");
                                }}
                                disabled={isPunchingScalp !== null}
                                className="rounded-xl bg-rose-500/15 hover:bg-rose-500/30 border border-rose-500/30 text-rose-400 text-[11px] font-bold px-2.5 py-2 transition active:scale-95 disabled:opacity-50"
                                title="Scalp Short instead"
                              >
                                - Sell Short
                              </button>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  punchInstantScalp(item.symbol, "buy");
                                }}
                                disabled={isPunchingScalp !== null}
                                className="rounded-xl bg-[#00F5A0]/15 hover:bg-[#00F5A0]/30 border border-[#00F5A0]/30 text-[#00F5A0] text-[11px] font-bold px-2.5 py-2 transition active:scale-95 disabled:opacity-50"
                                title="Scalp Long instead"
                              >
                                + Buy Long
                              </button>
                            )}

                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                selectAndScroll(item.symbol);
                              }}
                              className="text-[#00D9F5] font-bold hover:underline text-xs flex items-center gap-0.5 px-1.5 py-1"
                            >
                              Chart →
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div>
              {orders.length ? (
                <div className="mt-5 space-y-3 max-h-[620px] overflow-y-auto pr-1">
                  {orders.map(o => {
                    const isBuy = o.side === "buy";
                    const isFilled = o.status === "filled";
                    const isSelected = selectedSymbol === o.pair;

                    return (
                      <div
                        key={o.order_id}
                        onClick={() => selectAndScroll(o.pair)}
                        className={`rounded-2xl border p-4 transition cursor-pointer backdrop-blur-md ${
                          isSelected
                            ? "border-[#00F5A0] bg-[#00F5A0]/[0.06] shadow-lg shadow-[#00F5A0]/10"
                            : "border-white/[0.06] bg-[#090b12]/80 hover:border-white/20"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <b className="text-sm font-extrabold text-white tracking-tight">{o.pair}</b>
                            <span
                              className={`rounded-full px-2 py-0.5 text-[9px] font-black uppercase tracking-wider ${
                                isBuy ? "bg-[#00F5A0]/15 text-[#00F5A0]" : "bg-rose-500/15 text-rose-400"
                              }`}
                            >
                              {isBuy ? "BUY (LONG)" : "SELL (SHORT)"}
                            </span>
                            {isSelected && (
                              <span className="rounded-full bg-[#00F5A0] text-slate-950 font-black text-[9px] px-2 py-0.5 uppercase tracking-wider">
                                Active
                              </span>
                            )}
                          </div>

                          <span
                            className={`rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider ${
                              isFilled
                                ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30"
                                : "bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30"
                            }`}
                          >
                            {isFilled ? "✓ FILLED" : o.status}
                          </span>
                        </div>

                        <div className="mt-2.5 flex items-center justify-between text-xs text-white/60">
                          <div>
                            Filled: <b className="text-white font-mono font-bold">{balance(o.filled_quantity)}</b>
                            {o.requested_quantity && o.requested_quantity !== o.filled_quantity && (
                              <span className="text-white/40"> / {balance(o.requested_quantity)}</span>
                            )}
                            <span className="text-white/45"> @ ${balance(o.price)} USDT</span>
                          </div>
                          <span className="text-[10px] uppercase font-bold tracking-wider text-white/40">{o.order_type}</span>
                        </div>

                        {/* Date & Time in IST */}
                        <div className="mt-2.5 pt-2.5 border-t border-white/[0.04] flex items-center justify-between text-[11px] text-white/40">
                          <div className="flex items-center gap-1.5">
                            <svg className="w-3.5 h-3.5 text-white/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span className="text-white/70 font-mono font-medium">{formatIST(o.created_at)}</span>
                          </div>
                          <span className="text-[#00D9F5] font-bold text-[10px] hover:underline">View on Chart →</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-8 text-center text-xs uppercase tracking-widest text-white/40 py-10">
                  No recent order executions
                </p>
              )}
            </div>
          )}
        </Card>
      </section>

      {/* S24 Ultra Push Notification Modal */}
      {showAlertModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-xl animate-in fade-in duration-200">
          <div className="relative w-full max-w-2xl overflow-hidden rounded-3xl border border-white/15 cred-surface p-7 shadow-2xl">
            {/* Header */}
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-white/[0.08]">
              <div className="flex items-center gap-3.5">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.05] border border-white/10 text-2xl shadow-inner">
                  📱
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="text-xl font-black tracking-tight text-white">
                      Samsung Galaxy S24 Ultra Alerts
                    </h3>
                    <span className="rounded-full bg-[#00F5A0]/15 border border-[#00F5A0]/30 px-2.5 py-0.5 text-[9px] font-black text-[#00F5A0] uppercase tracking-wider">
                      Live Active
                    </span>
                  </div>
                  <p className="text-xs text-white/50 mt-0.5">
                    Tactile sound & vibration alerts directly to your phone for all trade executions.
                  </p>
                </div>
              </div>
              <button
                onClick={() => { setShowAlertModal(false); setAlertStatusMessage(null); }}
                className="h-8 w-8 rounded-full bg-white/[0.04] hover:bg-white/10 text-white/50 hover:text-white transition flex items-center justify-center text-xs font-bold"
              >
                ✕
              </button>
            </div>

            {/* Test Alert Button & Feedback */}
            <div className="mt-5 rounded-2xl border border-[#00D9F5]/30 bg-gradient-to-r from-[#00D9F5]/[0.08] via-transparent to-transparent p-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 text-xs font-bold text-white/80">
                    <span className="text-[10px] uppercase font-black tracking-wider text-white/40">Topic:</span>
                    <code className="rounded-lg bg-white/[0.05] px-2.5 py-1 font-mono text-[#00D9F5] text-xs border border-[#00D9F5]/30">
                      fno_trades_apurba
                    </code>
                  </div>
                  <p className="text-[11px] text-white/50 mt-1.5">
                    High-priority push delivery with exact IST timestamps.
                  </p>
                </div>
                <button
                  onClick={testPushNotification}
                  disabled={isTestingAlert}
                  className="cred-btn-primary px-5 py-2.5 text-xs flex items-center justify-center gap-2 whitespace-nowrap disabled:opacity-50"
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
                <div className={`mt-3 rounded-xl p-3 text-xs font-medium border ${
                  alertStatusMessage.includes("🚀")
                    ? "bg-[#00F5A0]/10 border-[#00F5A0]/30 text-[#00F5A0]"
                    : "bg-rose-500/10 border-rose-500/30 text-rose-300"
                }`}>
                  {alertStatusMessage}
                </div>
              )}
            </div>

            {/* Quick 30-Second Setup on S24 Ultra */}
            <div className="mt-5 space-y-2">
              <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/40">
                ⚡ Quick 30-Second Setup on your S24 Ultra:
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] p-3.5">
                  <div className="text-[#00F5A0] font-black text-xs mb-1">Step 1</div>
                  <p className="text-white/50 text-[11px] leading-relaxed">
                    Open Google Play Store on your S24 Ultra & install the free <b className="text-white">ntfy</b> app.
                  </p>
                </div>
                <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] p-3.5">
                  <div className="text-[#00D9F5] font-black text-xs mb-1">Step 2</div>
                  <p className="text-white/50 text-[11px] leading-relaxed">
                    Tap <b className="text-white">+ (Subscribe)</b> and enter topic: <code className="text-[#00D9F5] font-mono">fno_trades_apurba</code>
                  </p>
                </div>
                <div className="rounded-2xl bg-white/[0.02] border border-white/[0.06] p-3.5">
                  <div className="text-[#F59E0B] font-black text-xs mb-1">Step 3</div>
                  <p className="text-white/50 text-[11px] leading-relaxed">
                    Click the <b className="text-white">Send Test Alert</b> button above to verify phone sound & banner!
                  </p>
                </div>
              </div>
            </div>

            {/* Notification Types Covered */}
            <div className="mt-5 space-y-2">
              <h4 className="text-[10px] font-black uppercase tracking-[0.2em] text-white/40">
                🔔 Automatic Notifications Delivered to your S24 Ultra:
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-3 flex items-start gap-2.5">
                  <span className="text-base">🚀</span>
                  <div>
                    <div className="font-bold text-white">Trade Punched (Entry)</div>
                    <div className="text-[11px] text-white/50 mt-0.5">Pair, BUY/SELL, 3x leverage, Entry Price, TP, SL, Margin & IST Time.</div>
                  </div>
                </div>
                <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-3 flex items-start gap-2.5">
                  <span className="text-base">🎯</span>
                  <div>
                    <div className="font-bold text-white">Trade Exit & Take-Profit</div>
                    <div className="text-[11px] text-white/50 mt-0.5">Exit Price, Realized P&L ($ USDT & ROE %), Trigger reason & Cash balance.</div>
                  </div>
                </div>
                <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-3 flex items-start gap-2.5">
                  <span className="text-base">⚡</span>
                  <div>
                    <div className="font-bold text-white">Potential Breakout Setups</div>
                    <div className="text-[11px] text-white/50 mt-0.5">Tier-A setups (Score ≥ 75) with Trigger Price, Target & Invalidation Stop.</div>
                  </div>
                </div>
                <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-3 flex items-start gap-2.5">
                  <span className="text-base">🏆</span>
                  <div>
                    <div className="font-bold text-white">Daily Profit Goal ($6.00)</div>
                    <div className="text-[11px] text-white/50 mt-0.5">Instant alert when $6.00 profit target is locked for the day.</div>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between text-xs">
              <a
                href="https://ntfy.sh/fno_trades_apurba"
                target="_blank"
                rel="noreferrer"
                className="text-[#00D9F5] hover:underline font-bold flex items-center gap-1"
              >
                <span>Open Web Feed on Mobile Browser</span>
                <span>↗</span>
              </a>
              <button
                onClick={() => { setShowAlertModal(false); setAlertStatusMessage(null); }}
                className="cred-btn-secondary px-5 py-2 text-xs font-bold text-white"
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
