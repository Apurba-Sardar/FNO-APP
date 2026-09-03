"use client";

import { useEffect, useRef, useState } from "react";
import { money, balance } from "@/lib/format";

declare global {
  interface Window {
    TradingView?: any;
  }
}

export function normalizeTradingViewSymbol(symbol: string): string {
  const clean = symbol.replace(/^B-/, "").replace(/_/g, "");
  if (clean.includes("BTC")) return "BINANCE:BTCUSDT";
  if (clean.includes("ETH")) return "BINANCE:ETHUSDT";
  if (clean.includes("SOL")) return "BINANCE:SOLUSDT";
  if (clean.includes("XRP")) return "BINANCE:XRPUSDT";
  if (clean.includes("DOGE")) return "BINANCE:DOGEUSDT";
  if (clean.includes("LTC")) return "BINANCE:LTCUSDT";
  if (clean.includes("DOGS")) return "BINANCE:DOGSUSDT";
  if (clean.includes("ZEC")) return "BINANCE:ZECUSDT";
  if (clean.includes("1000CAT")) return "BINANCE:1000CATUSDT";
  if (clean.includes("MELANIA")) return "MEXC:MELANIAUSDT";
  if (clean.includes("MUBARAK")) return "MEXC:MUBARAKUSDT";
  if (clean.includes("AUCTION")) return "BINANCE:AUCTIONUSDT";
  return `BINANCE:${clean}`;
}

export type TradeDetailInfo = {
  pair: string;
  direction?: "long" | "short" | "buy" | "sell" | string;
  leverage?: number;
  quantity?: number;
  entryPrice?: number;
  markPrice?: number;
  targetPrice?: number;
  stopPrice?: number;
  margin?: number;
  unrealizedPnl?: number;
  entryTimeIST?: string;
  positionId?: string;
  orderType?: string;
  status?: string;
};

export function TradingViewChart({
  symbol = "B-XRP_USDT",
  tradeInfo,
  availableSymbols = [],
  onSelectSymbol,
  onExitPosition,
}: {
  symbol?: string;
  tradeInfo?: TradeDetailInfo | null;
  availableSymbols?: { symbol: string; label: string; pnl?: number; isRecent?: boolean }[];
  onSelectSymbol?: (sym: string) => void;
  onExitPosition?: (positionId: string, pair: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [currentSymbol, setCurrentSymbol] = useState(symbol);
  const [timeframe, setTimeframe] = useState("15");
  const [confirmExit, setConfirmExit] = useState(false);

  useEffect(() => {
    setCurrentSymbol(symbol);
  }, [symbol]);

  useEffect(() => {
    const tvSymbol = normalizeTradingViewSymbol(currentSymbol);
    const containerId = `tradingview_${Math.random().toString(36).substring(7)}`;

    if (containerRef.current) {
      containerRef.current.id = containerId;
    }

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/tv.js";
    script.async = true;
    script.onload = () => {
      if (window.TradingView && containerRef.current) {
        new window.TradingView.widget({
          autosize: true,
          symbol: tvSymbol,
          interval: timeframe,
          timezone: "Asia/Kolkata",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#090d16",
          enable_publishing: false,
          allow_symbol_change: true,
          container_id: containerId,
          hide_side_toolbar: false,
          studies: [
            "STD;EMA",
            "STD;RSI",
            "STD;MACD"
          ],
        });
      }
    };

    document.head.appendChild(script);

    return () => {
      if (script.parentNode) {
        script.parentNode.removeChild(script);
      }
    };
  }, [currentSymbol, timeframe]);

  const handleSymbolClick = (sym: string) => {
    setCurrentSymbol(sym);
    if (onSelectSymbol) onSelectSymbol(sym);
  };

  const isLong = tradeInfo?.direction?.toLowerCase().includes("long") || tradeInfo?.direction?.toLowerCase().includes("buy");
  const entry = tradeInfo?.entryPrice ? Number(tradeInfo.entryPrice) : null;
  const mark = tradeInfo?.markPrice ? Number(tradeInfo.markPrice) : null;
  const target = tradeInfo?.targetPrice ? Number(tradeInfo.targetPrice) : null;
  const stop = tradeInfo?.stopPrice ? Number(tradeInfo.stopPrice) : null;
  const pnl = tradeInfo?.unrealizedPnl != null ? Number(tradeInfo.unrealizedPnl) : null;
  const isProfit = pnl != null && pnl >= 0;

  // Calculate percentage gain from entry to mark
  const priceChangePct = (entry && mark && entry > 0) ? ((mark - entry) / entry) * 100 * (isLong ? 1 : -1) : null;

  return (
    <div className="w-full rounded-2xl border border-slate-800 bg-slate-950 shadow-2xl overflow-hidden">
      {/* Top Header & Trade Selection Bar */}
      <div className="border-b border-slate-800/80 bg-slate-900/60 p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <span className="h-3 w-3 animate-pulse rounded-full bg-emerald-400"></span>
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                Live Interactive Chart & Trade Visualizer
                <span className="text-xs font-mono font-normal text-slate-400 bg-slate-800/90 px-2 py-0.5 rounded border border-slate-700">
                  {normalizeTradingViewSymbol(currentSymbol)}
                </span>
              </h3>
              <p className="text-xs text-slate-400">
                Shows exact Entry, Mark Price, and Exit Targets in Indian Standard Time (IST)
              </p>
            </div>
          </div>

          {/* Timeframe selector */}
          <div className="flex items-center gap-1.5 self-start md:self-auto bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
            <span className="text-[11px] text-slate-500 px-2">Timeframe:</span>
            {["5", "15", "60", "240", "D"].map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`rounded px-2 py-1 font-bold transition ${
                  timeframe === tf ? "bg-emerald-500 text-slate-950" : "text-slate-400 hover:text-white"
                }`}
              >
                {tf === "D" ? "1D" : `${tf}m`}
              </button>
            ))}
          </div>
        </div>

        {/* Quick Trade Selector Pills */}
        <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-1 text-xs">
          <span className="text-slate-400 font-semibold text-[11px] shrink-0">Switch Trade:</span>
          {availableSymbols.length > 0 ? (
            availableSymbols.map(item => {
              const active = currentSymbol === item.symbol;
              const hasPnl = item.pnl != null;
              const isPnlPositive = (item.pnl ?? 0) >= 0;

              return (
                <button
                  key={item.symbol}
                  onClick={() => handleSymbolClick(item.symbol)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 shrink-0 transition font-bold ${
                    active
                      ? "bg-emerald-500 text-slate-950 shadow-md shadow-emerald-500/20"
                      : "bg-slate-950/80 border border-slate-800 text-slate-300 hover:border-slate-700 hover:text-white"
                  }`}
                >
                  <span>{item.label}</span>
                  {hasPnl && (
                    <span className={`text-[10px] font-black ${active ? "text-slate-950" : isPnlPositive ? "text-emerald-400" : "text-rose-400"}`}>
                      {isPnlPositive ? "+" : ""}{balance(item.pnl)}
                    </span>
                  )}
                  {item.isRecent && (
                    <span className="rounded bg-cyan-500/20 text-cyan-300 text-[9px] px-1">Recent</span>
                  )}
                </button>
              );
            })
          ) : (
            ["B-XRP_USDT", "B-DOGE_USDT", "B-DOGS_USDT", "B-1000CAT_USDT", "B-MELANIA_USDT", "B-MUBARAK_USDT", "B-ZEC_USDT"].map(sym => (
              <button
                key={sym}
                onClick={() => handleSymbolClick(sym)}
                className={`rounded-lg px-2.5 py-1.5 shrink-0 transition font-semibold ${
                  currentSymbol === sym
                    ? "bg-emerald-500 text-slate-950 font-bold"
                    : "bg-slate-950 border border-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {sym.replace("B-", "").replace("_USDT", "")}
              </button>
            ))
          )}
        </div>
      </div>

      {/* Trade Details HUD (Entry, Live Mark, Target, Stop, PnL) */}
      {tradeInfo && (
        <div className="bg-slate-900/90 border-b border-slate-800 p-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 text-xs">
            {/* Entry Box */}
            <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/20 p-3">
              <div className="flex items-center justify-between text-emerald-400 font-bold text-[11px]">
                <span>ENTRY PRICE</span>
                <span className="rounded bg-emerald-500/20 px-1 py-0.2 text-[10px] uppercase">
                  {isLong ? "BUY" : "SELL"}
                </span>
              </div>
              <p className="mt-1 text-base font-black text-white">
                ${money(entry)}
              </p>
              {tradeInfo.entryTimeIST && (
                <p className="mt-0.5 text-[10px] text-slate-400 truncate">
                  🕒 {tradeInfo.entryTimeIST}
                </p>
              )}
            </div>

            {/* Current Mark Price Box */}
            <div className="rounded-xl border border-slate-700 bg-slate-950/80 p-3">
              <div className="flex items-center justify-between text-slate-400 font-bold text-[11px]">
                <span>LIVE PRICE</span>
                {priceChangePct != null && (
                  <span className={`text-[10px] font-bold ${priceChangePct >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {priceChangePct >= 0 ? "+" : ""}{priceChangePct.toFixed(2)}%
                  </span>
                )}
              </div>
              <p className="mt-1 text-base font-black text-white">
                ${money(mark || entry)}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-500">Live Exchange Mark</p>
            </div>

            {/* Target Price (TP) Box */}
            <div className="rounded-xl border border-cyan-500/30 bg-cyan-950/20 p-3">
              <div className="flex items-center justify-between text-cyan-400 font-bold text-[11px]">
                <span>TARGET (TP)</span>
                <span className="text-[10px] text-cyan-300">Exit Profit</span>
              </div>
              <p className="mt-1 text-base font-black text-cyan-200">
                {target ? `$${money(target)}` : "Open Scalp"}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-500">
                {target && entry ? `+${(((target - entry) / entry) * 100).toFixed(1)}% gain target` : "Trailing Exit"}
              </p>
            </div>

            {/* Stop Loss (SL) Box */}
            <div className="rounded-xl border border-rose-500/30 bg-rose-950/20 p-3">
              <div className="flex items-center justify-between text-rose-400 font-bold text-[11px]">
                <span>STOP LOSS</span>
                <span className="text-[10px] text-rose-300">Safety Guard</span>
              </div>
              <p className="mt-1 text-base font-black text-rose-200">
                {stop ? `$${money(stop)}` : "Protected"}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-500">
                {stop && entry ? `-${(((entry - stop) / entry) * 100).toFixed(1)}% protection` : "Exchange Guard"}
              </p>
            </div>

            {/* Live Unrealized PnL Box */}
            <div className={`rounded-xl border p-3 ${isProfit ? "border-emerald-500/40 bg-emerald-950/30" : "border-rose-500/40 bg-rose-950/30"}`}>
              <div className="flex items-center justify-between font-bold text-[11px]">
                <span className={isProfit ? "text-emerald-400" : "text-rose-400"}>UNREALIZED P&L</span>
                <span className="text-[10px] text-slate-400">{tradeInfo.leverage ?? 1}x Isolated</span>
              </div>
              <p className={`mt-1 text-base font-black ${isProfit ? "text-emerald-300" : "text-rose-300"}`}>
                {pnl != null ? `${isProfit ? "+" : ""}${balance(pnl)} USDT` : "Active"}
              </p>
              <p className="mt-0.5 text-[10px] text-slate-400">
                Margin: ${balance(tradeInfo.margin)} USDT
              </p>
            </div>

            {/* Action / Exit Box */}
            <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 flex flex-col justify-between">
              <span className="text-[11px] font-bold text-slate-400 uppercase">Trade Control</span>
              {tradeInfo.positionId && onExitPosition ? (
                confirmExit ? (
                  <div className="flex gap-1 mt-1">
                    <button
                      onClick={() => {
                        onExitPosition(tradeInfo.positionId!, tradeInfo.pair);
                        setConfirmExit(false);
                      }}
                      className="flex-1 rounded bg-rose-600 hover:bg-rose-500 py-1 text-[10px] font-black text-white"
                    >
                      Confirm Exit
                    </button>
                    <button
                      onClick={() => setConfirmExit(false)}
                      className="rounded bg-slate-800 px-2 py-1 text-[10px] text-slate-300"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setConfirmExit(true)}
                    className="mt-1 w-full rounded-lg bg-rose-600/90 hover:bg-rose-500 py-1.5 text-xs font-bold text-white transition shadow-sm"
                  >
                    Take Profit / Exit
                  </button>
                )
              ) : (
                <div className="mt-1 text-[11px] text-emerald-400 font-semibold flex items-center gap-1">
                  <span>✓</span> {tradeInfo.status === "filled" ? "Filled Live Order" : "Active Monitored"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TradingView Candlestick Graph */}
      <div className="h-[540px] w-full" ref={containerRef} />
    </div>
  );
}
