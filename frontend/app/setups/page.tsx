"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";
import { formatIST, money } from "@/lib/format";

type Setup = {
  setup_id?: string;
  symbol: string;
  strategy: string;
  status: string;
  direction: string;
  setup_quality_score: number;
  opportunity_score: number;
  risk_reward: number | null;
  entry_zone: { low: number; high: number } | null;
  trigger_price: number | null;
  hypothetical_stop: number | null;
  hypothetical_target: number | null;
  expires_at: string | null;
  warnings: string[];
  evaluation_timestamp: string;
};

export default function SetupsPage() {
  const [rows, setRows] = useState<Setup[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<"all" | "actionable" | "long" | "short">("all");
  const [error, setError] = useState("");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${getApiUrl()}/setups?limit=500`)
      .then((response) => {
        if (!response.ok) throw new Error(`Failed to load setups (${response.status})`);
        return response.json();
      })
      .then((data) => setRows(data.items ?? []))
      .catch((cause) => setError(String(cause)));
  }, []);

  const copySetup = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2500);
  };

  const filtered = useMemo(() => {
    return rows.filter((row) => {
      const matches = row.symbol.toLowerCase().includes(query.toLowerCase());
      if (!matches) return false;
      if (filter === "actionable") return row.status?.toLowerCase() === "actionable" || row.status?.toLowerCase() === "triggered";
      if (filter === "long") return row.direction?.toLowerCase() === "long";
      if (filter === "short") return row.direction?.toLowerCase() === "short";
      return true;
    });
  }, [query, rows, filter]);

  return (
    <main className="mx-auto max-w-[1500px] p-4 sm:p-6 space-y-6">
      {/* Header Banner */}
      <header className="relative overflow-hidden rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 p-6 shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/30">
                <span>🎯</span> STRATEGY ENGINE & EXECUTION PLANS
              </span>
              <span className="text-xs text-slate-400 font-medium">
                Indian Standard Time (IST)
              </span>
            </div>
            <h1 className="mt-2 text-2xl sm:text-3xl font-black text-white">
              Actionable Strategy Breakouts & Setups
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Deterministic entry triggers, multi-timeframe confirmation zones, take-profit targets, and protective stops ready for live execution.
            </p>
          </div>

          <Link
            href="/live"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 px-5 py-2.5 text-xs font-bold text-white shadow-lg shadow-rose-600/20 transition"
          >
            <span>⚡</span> Open Live Approval Desk
          </Link>
        </div>
      </header>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-950/30 p-4 text-xs font-semibold text-rose-300">
          ⚠️ {error}
        </div>
      )}

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="flex flex-wrap rounded-xl border border-slate-800 bg-slate-900/80 p-1 text-xs font-semibold">
          <button
            onClick={() => setFilter("all")}
            className={`rounded-lg px-3.5 py-1.5 transition ${filter === "all" ? "bg-slate-800 text-white shadow" : "text-slate-400 hover:text-white"}`}
          >
            All Setups ({rows.length})
          </button>
          <button
            onClick={() => setFilter("actionable")}
            className={`rounded-lg px-3.5 py-1.5 transition ${filter === "actionable" ? "bg-emerald-500 text-slate-950 font-bold" : "text-slate-400 hover:text-white"}`}
          >
            Actionable / Triggered
          </button>
          <button
            onClick={() => setFilter("long")}
            className={`rounded-lg px-3.5 py-1.5 transition ${filter === "long" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" : "text-slate-400 hover:text-white"}`}
          >
            Bullish Longs
          </button>
          <button
            onClick={() => setFilter("short")}
            className={`rounded-lg px-3.5 py-1.5 transition ${filter === "short" ? "bg-rose-500/20 text-rose-300 border border-rose-500/40" : "text-slate-400 hover:text-white"}`}
          >
            Bearish Shorts
          </button>
        </div>

        <input
          type="text"
          placeholder="Search setup by coin (e.g. DOGE, XRP)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full sm:w-72 rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
        />
      </div>

      {/* Setup Cards Grid */}
      <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((s, idx) => {
          const isLong = s.direction?.toLowerCase() === "long";
          const idToCopy = s.setup_id || `setup_${s.symbol}_${s.strategy}`;

          return (
            <Card
              key={`${s.symbol}-${s.strategy}-${idx}`}
              className="p-5 bg-slate-900/60 border-slate-800 hover:border-slate-700 transition flex flex-col justify-between"
            >
              <div>
                {/* Symbol & Direction Header */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <b className="text-lg font-bold text-white">{s.symbol}</b>
                    <p className="text-xs text-slate-400 capitalize">
                      {s.strategy.replace(/_/g, " ")}
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span
                      className={`rounded px-2 py-0.5 text-[11px] font-black uppercase ${
                        isLong
                          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                          : "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                      }`}
                    >
                      {isLong ? "BUY · LONG" : "SELL · SHORT"}
                    </span>
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-bold text-slate-300">
                      Score: {s.setup_quality_score?.toFixed(1) ?? "—"}
                    </span>
                  </div>
                </div>

                {/* Trade Execution Levels Box */}
                <div className="mt-4 grid grid-cols-2 gap-2.5 rounded-xl bg-slate-950/80 p-3.5 border border-slate-800 text-xs">
                  <div>
                    <span className="text-slate-400 text-[11px]">Trigger Entry</span>
                    <p className="mt-0.5 font-bold text-white text-sm">
                      ${money(s.trigger_price)}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400 text-[11px]">Risk / Reward</span>
                    <p className="mt-0.5 font-bold text-cyan-300 text-sm">
                      {s.risk_reward ? `${s.risk_reward.toFixed(2)} R:R` : "2.00 R:R"}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-800/80">
                    <span className="text-slate-400 text-[11px]">Profit Target (TP)</span>
                    <p className="mt-0.5 font-bold text-emerald-400 text-sm">
                      ${money(s.hypothetical_target)}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-800/80">
                    <span className="text-slate-400 text-[11px]">Stop Loss (SL)</span>
                    <p className="mt-0.5 font-bold text-rose-400 text-sm">
                      ${money(s.hypothetical_stop)}
                    </p>
                  </div>
                </div>

                {/* Status & Expiry */}
                <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
                  <span>
                    Status: <b className="text-slate-200 capitalize">{s.status.replace(/_/g, " ")}</b>
                  </span>
                  {s.expires_at && (
                    <span>
                      Expires: <b className="text-slate-300">{formatIST(s.expires_at)}</b>
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between gap-2">
                <button
                  onClick={() => copySetup(idToCopy)}
                  className="rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 transition"
                >
                  {copiedId === idToCopy ? "✓ Copied Setup ID" : "Copy Setup ID"}
                </button>

                <Link
                  href="/live"
                  className="rounded-lg bg-emerald-500 hover:bg-emerald-400 px-3.5 py-1.5 text-xs font-bold text-slate-950 transition shadow"
                >
                  Execute Live →
                </Link>
              </div>
            </Card>
          );
        })}
      </section>
    </main>
  );
}
