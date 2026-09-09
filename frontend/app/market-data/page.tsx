"use client";

import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

const TIMEFRAMES = ["1w", "1d", "4h", "1h", "15m", "5m"];

type Market = { symbol: string; base_asset: string; quote_asset: string; status: string };
type Health = {
  rest: string;
  websocket: string;
  redis: string;
  database: string;
  last_market_update: string | null;
  stale: boolean;
};
type FrameResult = { candles: Array<{ timestamp: string; close: number }>; stale: boolean };
type Level = { price: number; strength: number; type: string };
type TimeframeAnalysis = {
  trend: string;
  trend_strength: number;
  indicators: {
    ema20: number | null;
    ema50: number | null;
    ema200: number | null;
    rsi: number | null;
    macd: number | null;
    macd_signal: number | null;
    atr: number | null;
    atr_percent: number | null;
    vwap: number | null;
    relative_volume: number | null;
  } | null;
  structure: {
    higher_high: boolean;
    higher_low: boolean;
    lower_high: boolean;
    lower_low: boolean;
    support_levels: Level[];
    resistance_levels: Level[];
  };
  data_quality: {
    sufficient_data: boolean;
    stale_data: boolean;
    analysis_completeness: number;
    warnings: string[];
  };
};
type Analysis = {
  timeframes: Record<string, TimeframeAnalysis>;
  alignment: { alignment_state: string; alignment_ratio: number };
  data_quality: { sufficient_data: boolean; analysis_completeness: number };
};

const show = (value: number | null | undefined, digits = 4) =>
  value == null ? "—" : value.toLocaleString(undefined, { maximumFractionDigits: digits });

export default function MarketDataPage() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [selected, setSelected] = useState("");
  const [query, setQuery] = useState("");
  const [frames, setFrames] = useState<Record<string, FrameResult>>({});
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analysisFrame, setAnalysisFrame] = useState("15m");
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);

  useEffect(() => {
    const api = getApiUrl();
    Promise.all([
      fetch(`${api}/markets`).then((response) => response.json()),
      fetch(`${api}/health/market-data`).then((response) => response.json()),
    ])
      .then(([marketData, healthData]) => {
        setMarkets(marketData.items ?? []);
        setHealth(healthData);
        if (marketData.items?.length) setSelected(marketData.items[0].symbol);
      })
      .catch((cause) => setError(String(cause)));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setLoadingAnalysis(true);
    setError("");
    const api = getApiUrl();
    Promise.all([
      fetch(`${api}/markets/${encodeURIComponent(selected)}/multi-timeframe?limit=200`).then(
        (response) => response.json(),
      ),
      fetch(`${api}/markets/${encodeURIComponent(selected)}/ticker`).then((response) =>
        response.json(),
      ),
      fetch(`${api}/analysis/${encodeURIComponent(selected)}`).then((response) => {
        if (!response.ok) throw new Error(`analysis request failed (${response.status})`);
        return response.json();
      }),
    ])
      .then(([multi, ticker, analysisData]) => {
        setFrames(multi.results ?? {});
        setLatestPrice(ticker.ticker?.last_price ?? ticker.ticker?.mark_price ?? null);
        setAnalysis(analysisData);
      })
      .catch((cause) => setError(String(cause)))
      .finally(() => setLoadingAnalysis(false));
  }, [selected]);

  const filtered = useMemo(
    () => markets.filter((market) => market.symbol.toLowerCase().includes(query.toLowerCase())),
    [markets, query],
  );
  const latestCandle = Object.values(frames)
    .flatMap((frame) => frame.candles.slice(-1))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0];
  const selectedAnalysis = analysis?.timeframes[analysisFrame];
  const indicators = selectedAnalysis?.indicators;

  return (
    <main className="mx-auto max-w-[1600px] p-4 sm:p-8 space-y-7">
      {/* Header Banner - CRED Velvet Matte Obsidian */}
      <header className="cred-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.9)]">
        {/* Subtle Ambient Radial Glows */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-[#00D9F5]/10 blur-3xl"></div>
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-[#00F5A0]/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#00D9F5]/10 px-3 py-1 text-[11px] font-black tracking-wider uppercase text-[#00D9F5] border border-[#00D9F5]/30 shadow-[0_0_15px_rgba(0,217,245,0.2)]">
                <span>📊</span> Real-Time Quantitative Streams
              </span>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                CoinDCX Futures Depth & Telemetry
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Futures Market Analysis & Depth
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              Real-time multi-timeframe candle streams, algorithmic trend alignment, EMAs, RSI, and technical market structure.
            </p>
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs font-semibold text-rose-300 shadow-lg">
          ⚠️ {error}
        </div>
      )}

      {/* Health Metric Cards */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">USDT Futures Pairs</p>
          <p className="mt-2 text-2xl font-black text-white font-mono">{markets.length}</p>
          <span className="mt-1 block text-[11px] text-slate-400">Available trade contracts</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">REST API Gateway</p>
          <p className="mt-2 text-2xl font-black text-[#00F5A0] font-mono capitalize">{health?.rest ?? "Syncing..."}</p>
          <span className="mt-1 block text-[11px] text-slate-400">CoinDCX exchange connector</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">WebSocket Stream</p>
          <p className="mt-2 text-2xl font-black text-[#00D9F5] font-mono capitalize">{health?.websocket ?? "Syncing..."}</p>
          <span className="mt-1 block text-[11px] text-slate-400">Low-latency live prices</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Last Telemetry Sync</p>
          <p className="mt-2 text-base font-bold text-white font-mono truncate">
            {health?.last_market_update ? new Date(health.last_market_update).toLocaleTimeString() : "—"}
          </p>
          <span className="mt-1 block text-[11px] text-slate-400">Automatic tick pulse</span>
        </Card>
      </section>

      {/* Main Content Layout */}
      <section className="grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* Left Market Selector List */}
        <Card className="max-h-[820px] p-5 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl flex flex-col">
          <input
            className="mb-4 w-full rounded-xl border border-white/[0.08] bg-[#07070a] px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#00D9F5] focus:ring-1 focus:ring-[#00D9F5]/30 transition"
            placeholder="Search markets (e.g. BTC, ETH)..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="flex-1 space-y-1.5 overflow-y-auto pr-1">
            {filtered.map((market) => (
              <button
                className={`w-full rounded-xl px-3.5 py-2.5 text-left text-xs font-mono font-bold transition-all duration-200 ${
                  selected === market.symbol
                    ? "bg-[#00D9F5] text-black shadow-[0_0_15px_rgba(0,217,245,0.3)]"
                    : "text-slate-300 hover:bg-white/[0.04] border border-transparent hover:border-white/[0.05]"
                }`}
                key={market.symbol}
                onClick={() => setSelected(market.symbol)}
              >
                {market.symbol}
              </button>
            ))}
          </div>
        </Card>

        {/* Right Detail Pane */}
        <div className="space-y-6">
          {/* Market Overview Card */}
          <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Selected Market</p>
                <p className="mt-1 text-3xl font-black text-white font-mono">{selected || "—"}</p>
              </div>
              <div className="text-right">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Analysis Alignment</p>
                <p className="mt-1 text-base font-black uppercase text-[#00D9F5] font-mono">
                  {loadingAnalysis
                    ? "Calculating..."
                    : analysis?.alignment.alignment_state.replaceAll("_", " ") ?? "—"}
                </p>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-4 pt-5 border-t border-white/[0.06]">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Latest Mark / Last Price</p>
                <p className="mt-1 text-2xl font-black text-white font-mono">${show(latestPrice)}</p>
              </div>
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Latest Candle Close</p>
                <p className="mt-1 text-2xl font-black text-[#00F5A0] font-mono">${show(latestCandle?.close)}</p>
              </div>
            </div>
          </Card>

          {/* Timeframe Analysis Tabs */}
          <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
            <div className="flex items-center justify-between gap-2 mb-4">
              <h2 className="text-base font-black text-white tracking-tight">Timeframe Analysis</h2>
              <span className="text-xs text-slate-500 font-mono">Select frame for deep indicator inspection</span>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {TIMEFRAMES.map((frame) => {
                const item = analysis?.timeframes[frame];
                const isSelected = analysisFrame === frame;
                return (
                  <button
                    className={`rounded-2xl border p-3.5 text-left transition-all duration-200 ${
                      isSelected
                        ? "border-[#00D9F5] bg-[#00D9F5]/10 shadow-[0_0_15px_rgba(0,217,245,0.2)]"
                        : "border-white/[0.06] bg-[#060608] hover:border-white/[0.15]"
                    }`}
                    key={frame}
                    onClick={() => setAnalysisFrame(frame)}
                  >
                    <p className={`text-[10px] font-black uppercase tracking-wider ${isSelected ? "text-[#00D9F5]" : "text-slate-500"}`}>
                      {frame}
                    </p>
                    <p className="mt-1 font-bold text-white capitalize text-xs">{item?.trend ?? "Syncing"}</p>
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                      Str: {item ? show(item.trend_strength, 1) : "—"}
                    </p>
                  </button>
                );
              })}
            </div>
          </Card>

          {/* Indicators & Structure Grid */}
          <div className="grid gap-6 xl:grid-cols-2">
            <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
              <h2 className="text-base font-black text-white tracking-tight mb-4">
                Indicators · <span className="text-[#00D9F5] font-mono">{analysisFrame}</span>
              </h2>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-xs">
                {[
                  ["EMA20", indicators?.ema20],
                  ["EMA50", indicators?.ema50],
                  ["EMA200", indicators?.ema200],
                  ["RSI 14", indicators?.rsi],
                  ["MACD", indicators?.macd],
                  ["MACD Signal", indicators?.macd_signal],
                  ["ATR", indicators?.atr],
                  ["ATR %", indicators?.atr_percent],
                  ["UTC VWAP", indicators?.vwap],
                  ["Relative Volume", indicators?.relative_volume],
                ].map(([label, value]) => (
                  <div className="flex items-center justify-between gap-3 p-2 rounded-xl bg-white/[0.02] border border-white/[0.04]" key={String(label)}>
                    <dt className="text-slate-400 font-medium">{label}</dt>
                    <dd className="font-mono font-bold text-white">{show(value as number | null)}</dd>
                  </div>
                ))}
              </dl>
            </Card>

            <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
              <h2 className="text-base font-black text-white tracking-tight mb-4">
                Structure · <span className="text-[#00F5A0] font-mono">{analysisFrame}</span>
              </h2>
              <div className="grid grid-cols-2 gap-3 text-xs mb-4">
                <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04] flex justify-between">
                  <span className="text-slate-400">Higher High</span>
                  <b className={selectedAnalysis?.structure.higher_high ? "text-[#00F5A0]" : "text-slate-500"}>
                    {selectedAnalysis?.structure.higher_high ? "YES" : "NO"}
                  </b>
                </div>
                <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04] flex justify-between">
                  <span className="text-slate-400">Higher Low</span>
                  <b className={selectedAnalysis?.structure.higher_low ? "text-[#00F5A0]" : "text-slate-500"}>
                    {selectedAnalysis?.structure.higher_low ? "YES" : "NO"}
                  </b>
                </div>
                <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04] flex justify-between">
                  <span className="text-slate-400">Lower High</span>
                  <b className={selectedAnalysis?.structure.lower_high ? "text-[#FF3366]" : "text-slate-500"}>
                    {selectedAnalysis?.structure.lower_high ? "YES" : "NO"}
                  </b>
                </div>
                <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/[0.04] flex justify-between">
                  <span className="text-slate-400">Lower Low</span>
                  <b className={selectedAnalysis?.structure.lower_low ? "text-[#FF3366]" : "text-slate-500"}>
                    {selectedAnalysis?.structure.lower_low ? "YES" : "NO"}
                  </b>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs pt-4 border-t border-white/[0.06]">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.15em] text-[#00F5A0] mb-2">Key Support</p>
                  {selectedAnalysis?.structure.support_levels.length ? (
                    selectedAnalysis.structure.support_levels.map((level) => (
                      <p className="font-mono text-slate-300 text-xs py-0.5" key={`${level.price}-${level.strength}`}>
                        ${show(level.price)} <span className="text-slate-500 font-normal">· str {level.strength}</span>
                      </p>
                    ))
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </div>
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.15em] text-[#FF3366] mb-2">Key Resistance</p>
                  {selectedAnalysis?.structure.resistance_levels.length ? (
                    selectedAnalysis.structure.resistance_levels.map((level) => (
                      <p className="font-mono text-slate-300 text-xs py-0.5" key={`${level.price}-${level.strength}`}>
                        ${show(level.price)} <span className="text-slate-500 font-normal">· str {level.strength}</span>
                      </p>
                    ))
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </div>
              </div>
            </Card>
          </div>

          {/* Data Quality Card */}
          <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-base font-black text-white tracking-tight">Data Quality & Completeness</h2>
              <span
                className={`rounded-full px-3 py-1 text-xs font-black uppercase tracking-wider ${
                  analysis?.data_quality.sufficient_data
                    ? "bg-[#00F5A0]/10 text-[#00F5A0] border border-[#00F5A0]/30"
                    : "bg-[#FFB800]/10 text-[#FFB800] border border-[#FFB800]/30"
                }`}
              >
                {analysis?.data_quality.sufficient_data ? "Healthy Data Feed" : "Feed Degradation"}
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-400 font-mono">
              Analysis Completeness: <b className="text-white">{show(analysis?.data_quality.analysis_completeness, 1)}%</b>
            </p>
            {selectedAnalysis?.data_quality.warnings.length ? (
              <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-300">
                {selectedAnalysis.data_quality.warnings.slice(0, 4).map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            ) : null}
          </Card>
        </div>
      </section>
    </main>
  );
}
