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
  const [currentSymbol, setCurrentSymbol] = useState(symbol);
  const [timeframe, setTimeframe] = useState("15");
  const [confirmExit, setConfirmExit] = useState(false);

  useEffect(() => {
    setCurrentSymbol(symbol);
  }, [symbol]);

  const tvSymbol = normalizeTradingViewSymbol(currentSymbol);
  const embedUrl = `https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol=${encodeURIComponent(tvSymbol)}&interval=${timeframe}&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=090d16&theme=dark&style=1&timezone=Asia%2FKolkata`;

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
    <div className="w-full rounded-3xl cred-surface shadow-[0_25px_60px_rgba(0,0,0,0.9)] overflow-hidden">
      {/* Top Header & Trade Selection Bar */}
      <div className="border-b border-white/[0.08] bg-black/40 p-4 sm:p-5 backdrop-blur-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-[#00F5A0]/15 border border-[#00F5A0]/30 flex items-center justify-center text-[#00F5A0] shadow-[0_0_15px_rgba(0,245,160,0.2)]">
              <span className="text-base">📈</span>
            </div>
            <div>
              <h3 className="text-base font-black text-white flex items-center gap-2 tracking-tight">
                Live Interactive Chart & Trade Visualizer
                <span className="text-xs font-mono font-bold text-[#00F5A0] bg-[#00F5A0]/10 px-2.5 py-0.5 rounded-full border border-[#00F5A0]/20">
                  {normalizeTradingViewSymbol(currentSymbol)}
                </span>
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Exact Entry, Mark Price, and Protection Bounds streaming live in Indian Standard Time (IST)
              </p>
            </div>
          </div>

          {/* Timeframe selector */}
          <div className="flex items-center gap-1 self-start md:self-auto bg-black/60 p-1 rounded-xl border border-white/[0.08] text-xs shadow-inner">
            <span className="text-[10px] uppercase font-black tracking-wider text-slate-500 px-2">TF:</span>
            {["5", "15", "60", "240", "D"].map(tf => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`rounded-lg px-2.5 py-1 text-xs font-black transition ${
                  timeframe === tf
                    ? "bg-[#00F5A0] text-black shadow-[0_0_15px_rgba(0,245,160,0.4)]"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`}
              >
                {tf === "D" ? "1D" : `${tf}m`}
              </button>
            ))}
          </div>
        </div>

        {/* Quick Trade Selector Pills */}
        <div className="mt-3.5 flex items-center gap-2 overflow-x-auto pb-1 text-xs">
          <span className="text-slate-400 font-bold text-[10px] uppercase tracking-wider shrink-0">Select Pair:</span>
          {availableSymbols.length > 0 ? (
            availableSymbols.map(item => {
              const active = currentSymbol === item.symbol;
              const hasPnl = item.pnl != null;
              const isPnlPositive = (item.pnl ?? 0) >= 0;

              return (
                <button
                  key={item.symbol}
                  onClick={() => handleSymbolClick(item.symbol)}
                  className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 shrink-0 transition font-black text-xs ${
                    active
                      ? "bg-[#00F5A0] text-black shadow-[0_0_20px_rgba(0,245,160,0.35)]"
                      : "bg-white/[0.04] border border-white/[0.08] text-slate-300 hover:border-white/20 hover:text-white"
                  }`}
                >
                  <span>{item.label}</span>
                  {hasPnl && (
                    <span className={`text-[10px] font-black ${active ? "text-black" : isPnlPositive ? "text-emerald-400" : "text-rose-400"}`}>
                      {isPnlPositive ? "+" : ""}{balance(item.pnl)}
                    </span>
                  )}
                  {item.isRecent && (
                    <span className="rounded-full bg-cyan-400/20 text-cyan-300 text-[9px] px-1.5 font-extrabold uppercase">Live</span>
                  )}
                </button>
              );
            })
          ) : (
            ["B-XRP_USDT", "B-DOGE_USDT", "B-SOL_USDT", "B-ETH_USDT", "B-BTC_USDT", "B-LTC_USDT"].map(sym => (
              <button
                key={sym}
                onClick={() => handleSymbolClick(sym)}
                className={`rounded-xl px-3 py-1.5 shrink-0 transition font-bold text-xs ${
                  currentSymbol === sym
                    ? "bg-[#00F5A0] text-black font-black"
                    : "bg-white/[0.04] border border-white/[0.08] text-slate-400 hover:text-white hover:border-white/20"
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
        <div className="bg-black/60 border-b border-white/[0.08] p-4 sm:p-5 backdrop-blur-xl">
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
      <div className="h-[560px] w-full bg-[#090d16]">
        <iframe
          key={`${tvSymbol}-${timeframe}`}
          src={embedUrl}
          className="w-full h-full border-0"
          title={`TradingView Chart ${tvSymbol}`}
          allow="clipboard-write"
          loading="lazy"
        />
      </div>
    </div>
  );
}
