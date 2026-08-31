"use client";

import { useEffect, useMemo, useState } from "react";

import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export default function MarketDataPage() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [selected, setSelected] = useState<string>("");
  const [query, setQuery] = useState("");
  const [frames, setFrames] = useState<Record<string, FrameResult>>({});
  const [latestPrice, setLatestPrice] = useState<number | null>(null);
  const [error, setError] = useState<string>("");

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
    Promise.all([
      fetch(`${API}/api/v1/markets/${encodeURIComponent(selected)}/multi-timeframe?limit=200`).then(
        (response) => response.json(),
      ),
      fetch(`${API}/api/v1/markets/${encodeURIComponent(selected)}/ticker`).then((response) =>
        response.json(),
      ),
    ])
      .then(([multi, ticker]) => {
        setFrames(multi.results ?? {});
        setLatestPrice(ticker.ticker?.last_price ?? ticker.ticker?.mark_price ?? null);
      })
      .catch((cause) => setError(String(cause)));
  }, [selected]);

  const filtered = useMemo(
    () => markets.filter((market) => market.symbol.toLowerCase().includes(query.toLowerCase())),
    [markets, query],
  );
  const latestCandle = Object.values(frames)
    .flatMap((frame) => frame.candles.slice(-1))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0];

  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6">
      <header className="mb-6">
        <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">Phase 2 developer view</p>
        <h1 className="text-2xl font-semibold">CoinDCX futures market data</h1>
        <p className="mt-1 text-sm text-slate-400">Read-only pipeline validation. No trading controls.</p>
      </header>
      {error && <p className="mb-4 rounded-lg bg-red-950 p-3 text-sm text-red-300">{error}</p>}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card><p className="text-sm text-slate-400">USDT futures</p><p className="mt-2 text-2xl font-semibold">{markets.length}</p></Card>
        <Card><p className="text-sm text-slate-400">REST</p><p className="mt-2 text-xl font-semibold">{health?.rest ?? "loading"}</p></Card>
        <Card><p className="text-sm text-slate-400">WebSocket</p><p className="mt-2 text-xl font-semibold">{health?.websocket ?? "loading"}</p></Card>
        <Card><p className="text-sm text-slate-400">Last update</p><p className="mt-2 text-sm font-medium">{health?.last_market_update ? new Date(health.last_market_update).toLocaleString() : "—"}</p></Card>
      </section>
      <section className="mt-4 grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card className="max-h-[620px] overflow-hidden">
          <input className="mb-3 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" placeholder="Search markets" value={query} onChange={(event) => setQuery(event.target.value)} />
          <div className="max-h-[540px] space-y-1 overflow-y-auto">
            {filtered.map((market) => <button className={`w-full rounded-md px-3 py-2 text-left text-sm ${selected === market.symbol ? "bg-cyan-500 text-slate-950" : "hover:bg-slate-800"}`} key={market.symbol} onClick={() => setSelected(market.symbol)}>{market.symbol}</button>)}
          </div>
        </Card>
        <div className="space-y-4">
          <Card><p className="text-sm text-slate-400">Selected symbol</p><p className="mt-2 text-2xl font-semibold">{selected || "—"}</p><div className="mt-4 grid grid-cols-2 gap-4"><div><p className="text-xs text-slate-500">Latest price</p><p className="text-lg">{latestPrice ?? "—"}</p></div><div><p className="text-xs text-slate-500">Latest candle close</p><p className="text-lg">{latestCandle?.close ?? "—"}</p></div></div></Card>
          <Card><h2 className="font-medium">Candle counts</h2><div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">{["1w", "1d", "4h", "1h", "15m", "5m"].map((frame) => <div className="rounded-lg bg-slate-950 p-3" key={frame}><p className="text-xs uppercase text-slate-500">{frame}</p><p className="mt-1 text-xl">{frames[frame]?.candles.length ?? 0}</p><p className="text-xs text-slate-500">{frames[frame]?.stale ? "stale" : "current"}</p></div>)}</div></Card>
        </div>
      </section>
    </main>
  );
}
