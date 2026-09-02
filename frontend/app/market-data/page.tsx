"use client";

import { useEffect, useMemo, useState } from "react";

import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
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
    Promise.all([
      fetch(`${API}/api/v1/markets`).then((response) => response.json()),
      fetch(`${API}/api/v1/health/market-data`).then((response) => response.json()),
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
    Promise.all([
      fetch(`${API}/api/v1/markets/${encodeURIComponent(selected)}/multi-timeframe?limit=200`).then(
        (response) => response.json(),
      ),
      fetch(`${API}/api/v1/markets/${encodeURIComponent(selected)}/ticker`).then((response) =>
        response.json(),
      ),
      fetch(`${API}/api/v1/analysis/${encodeURIComponent(selected)}`).then((response) => {
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
    <main className="mx-auto max-w-7xl p-4 sm:p-6">
      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">
          Phase 3 developer view
        </p>
        <h1 className="text-2xl font-semibold">Futures market analysis</h1>
        <p className="mt-1 text-sm text-slate-400">
          Read-only quantitative analysis. No recommendations or trading controls.
        </p>
      </header>

      {error && <p className="mb-4 rounded-lg bg-red-950 p-3 text-sm text-red-300">{error}</p>}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-sm text-slate-400">USDT futures</p>
          <p className="mt-2 text-2xl font-semibold">{markets.length}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-400">REST</p>
          <p className="mt-2 text-xl font-semibold">{health?.rest ?? "loading"}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-400">WebSocket</p>
          <p className="mt-2 text-xl font-semibold">{health?.websocket ?? "loading"}</p>
        </Card>
        <Card>
          <p className="text-sm text-slate-400">Last update</p>
          <p className="mt-2 text-sm font-medium">
            {health?.last_market_update
              ? new Date(health.last_market_update).toLocaleString()
              : "—"}
          </p>
        </Card>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-[300px_1fr]">
        <Card className="max-h-[760px] overflow-hidden">
          <input
            className="mb-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            placeholder="Search markets"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <div className="max-h-[680px] space-y-1 overflow-y-auto">
            {filtered.map((market) => (
              <button
                className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                  selected === market.symbol
                    ? "bg-cyan-500 text-slate-950"
                    : "hover:bg-slate-800"
                }`}
                key={market.symbol}
                onClick={() => setSelected(market.symbol)}
              >
                {market.symbol}
              </button>
            ))}
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm text-slate-400">Market</p>
                <p className="mt-1 text-2xl font-semibold">{selected || "—"}</p>
              </div>
              <div className="text-right text-sm">
                <p className="text-slate-400">Analysis alignment</p>
                <p className="font-medium uppercase text-cyan-300">
                  {loadingAnalysis
                    ? "calculating"
                    : analysis?.alignment.alignment_state.replaceAll("_", " ") ?? "—"}
                </p>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-slate-500">Latest price</p>
                <p className="text-lg">{show(latestPrice)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Latest candle close</p>
                <p className="text-lg">{show(latestCandle?.close)}</p>
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between gap-2">
              <h2 className="font-medium">Timeframe analysis</h2>
              <span className="text-xs text-slate-500">Select a frame for details</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 md:grid-cols-3">
              {TIMEFRAMES.map((frame) => {
                const item = analysis?.timeframes[frame];
                return (
                  <button
                    className={`rounded-lg border p-3 text-left ${
                      analysisFrame === frame
                        ? "border-cyan-500 bg-cyan-950/40"
                        : "border-slate-800 bg-slate-950"
                    }`}
                    key={frame}
                    onClick={() => setAnalysisFrame(frame)}
                  >
                    <p className="text-xs uppercase text-slate-500">{frame}</p>
                    <p className="mt-1 capitalize">{item?.trend ?? "unavailable"}</p>
                    <p className="text-xs text-slate-400">
                      Strength {item ? show(item.trend_strength, 1) : "—"}/100
                    </p>
                  </button>
                );
              })}
            </div>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <h2 className="font-medium">Indicators · {analysisFrame}</h2>
              <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
                {[
                  ["EMA20", indicators?.ema20],
                  ["EMA50", indicators?.ema50],
                  ["EMA200", indicators?.ema200],
                  ["RSI14", indicators?.rsi],
                  ["MACD", indicators?.macd],
                  ["MACD signal", indicators?.macd_signal],
                  ["ATR", indicators?.atr],
                  ["ATR %", indicators?.atr_percent],
                  ["UTC VWAP", indicators?.vwap],
                  ["Relative volume", indicators?.relative_volume],
                ].map(([label, value]) => (
                  <div className="flex justify-between gap-3" key={String(label)}>
                    <dt className="text-slate-500">{label}</dt>
                    <dd>{show(value as number | null)}</dd>
                  </div>
                ))}
              </dl>
            </Card>

            <Card>
              <h2 className="font-medium">Structure · {analysisFrame}</h2>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                <p>Higher high: {selectedAnalysis?.structure.higher_high ? "yes" : "no"}</p>
                <p>Higher low: {selectedAnalysis?.structure.higher_low ? "yes" : "no"}</p>
                <p>Lower high: {selectedAnalysis?.structure.lower_high ? "yes" : "no"}</p>
                <p>Lower low: {selectedAnalysis?.structure.lower_low ? "yes" : "no"}</p>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-slate-500">Potential support</p>
                  {selectedAnalysis?.structure.support_levels.length
                    ? selectedAnalysis.structure.support_levels.map((level) => (
                        <p key={`${level.price}-${level.strength}`}>
                          {show(level.price)} · strength {level.strength}
                        </p>
                      ))
                    : "—"}
                </div>
                <div>
                  <p className="text-slate-500">Potential resistance</p>
                  {selectedAnalysis?.structure.resistance_levels.length
                    ? selectedAnalysis.structure.resistance_levels.map((level) => (
                        <p key={`${level.price}-${level.strength}`}>
                          {show(level.price)} · strength {level.strength}
                        </p>
                      ))
                    : "—"}
                </div>
              </div>
            </Card>
          </div>

          <Card>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-medium">Data quality</h2>
              <span
                className={`rounded-full px-3 py-1 text-xs ${
                  analysis?.data_quality.sufficient_data
                    ? "bg-emerald-950 text-emerald-300"
                    : "bg-amber-950 text-amber-300"
                }`}
              >
                {analysis?.data_quality.sufficient_data ? "Healthy" : "Warning"}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-400">
              Analysis completeness: {show(analysis?.data_quality.analysis_completeness, 1)}%
            </p>
            {selectedAnalysis?.data_quality.warnings.length ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-amber-300">
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
