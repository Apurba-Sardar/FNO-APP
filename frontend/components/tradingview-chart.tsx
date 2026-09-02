"use client";

import { useEffect, useRef, useState } from "react";

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
  if (clean.includes("DOGS")) return "BINANCE:DOGSUSDT";
  if (clean.includes("ZEC")) return "BINANCE:ZECUSDT";
  if (clean.includes("1000CAT")) return "BINANCE:1000CATUSDT";
  if (clean.includes("MELANIA")) return "MEXC:MELANIAUSDT";
  if (clean.includes("MUBARAK")) return "MEXC:MUBARAKUSDT";
  return `BINANCE:${clean}`;
}

export function TradingViewChart({ symbol = "B-DOGS_USDT" }: { symbol?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [currentSymbol, setCurrentSymbol] = useState(symbol);

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
          interval: "15",
          timezone: "Asia/Kolkata",
          theme: "dark",
          style: "1",
          locale: "en",
          toolbar_bg: "#0f172a",
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
  }, [currentSymbol]);

  return (
    <div className="w-full rounded-2xl border border-slate-800 bg-slate-950 p-4 shadow-2xl">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-emerald-400"></span>
          <h3 className="font-bold text-slate-100">Live TradingView Chart</h3>
          <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
            {normalizeTradingViewSymbol(currentSymbol)}
          </span>
        </div>
        <div className="flex gap-1.5 text-xs">
          {["B-DOGS_USDT", "B-MELANIA_USDT", "B-1000CAT_USDT", "B-MUBARAK_USDT", "B-ZEC_USDT", "B-BTC_USDT"].map(sym => (
            <button
              key={sym}
              onClick={() => setCurrentSymbol(sym)}
              className={`rounded px-2.5 py-1 transition ${
                currentSymbol === sym ? "bg-emerald-500 font-bold text-slate-950" : "bg-slate-900 text-slate-400 hover:text-slate-200"
              }`}
            >
              {sym.replace("B-", "").replace("_USDT", "")}
            </button>
          ))}
        </div>
      </div>
      <div className="h-[520px] w-full overflow-hidden rounded-xl border border-slate-900" ref={containerRef} />
    </div>
  );
}
