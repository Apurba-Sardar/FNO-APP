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
    <main className="mx-auto max-w-[1600px] p-4 sm:p-8 space-y-7">
      {/* Header Banner - CRED Velvet Matte Obsidian */}
      <header className="cred-surface relative overflow-hidden rounded-3xl p-6 sm:p-8 shadow-[0_25px_60px_rgba(0,0,0,0.9)]">
        {/* Subtle Ambient Radial Glows */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-[#00F5A0]/10 blur-3xl"></div>
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-[#00D9F5]/10 blur-3xl"></div>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#00F5A0]/10 px-3 py-1 text-[11px] font-black tracking-wider uppercase text-[#00F5A0] border border-[#00F5A0]/30 shadow-[0_0_15px_rgba(0,245,160,0.2)]">
                <span>🎯</span> Strategy Engine & Execution Plans
              </span>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                Indian Standard Time (IST) Active
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Actionable Strategy Breakouts & Setups
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              Deterministic entry triggers, multi-timeframe confirmation zones, take-profit targets, and protective stops ready for live execution.
            </p>
          </div>

          <Link
            href="/live"
            className="cred-btn-primary rounded-xl px-5 py-2.5 text-xs font-black flex items-center gap-2 self-start lg:self-auto"
          >
            <span>⚡</span> Open Live Trading Suite
          </Link>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs font-semibold text-rose-300 shadow-lg">
          ⚠️ {error}
        </div>
      )}

      {/* Filter Tabs & Search */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <div className="flex flex-wrap rounded-2xl border border-white/[0.07] bg-[#0a0a0d] p-1.5 text-xs font-semibold shadow-inner">
          <button
            onClick={() => setFilter("all")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              filter === "all"
                ? "bg-white/[0.1] text-white shadow-[0_2px_8px_rgba(0,0,0,0.5)] border border-white/[0.1]"
                : "text-slate-400 hover:text-white"
            }`}
          >
            All Setups ({rows.length})
          </button>
          <button
            onClick={() => setFilter("actionable")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              filter === "actionable"
                ? "bg-[#00F5A0] text-black font-black shadow-[0_0_15px_rgba(0,245,160,0.4)]"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Actionable / Triggered
          </button>
          <button
            onClick={() => setFilter("long")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              filter === "long"
                ? "bg-[#00F5A0]/20 text-[#00F5A0] border border-[#00F5A0]/40 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Bullish Longs
          </button>
          <button
            onClick={() => setFilter("short")}
            className={`rounded-xl px-4 py-2 transition-all duration-200 ${
              filter === "short"
                ? "bg-[#FF3366]/20 text-[#FF3366] border border-[#FF3366]/40 font-bold"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Bearish Shorts
          </button>
        </div>

        <input
          type="text"
          placeholder="Search setup by coin (e.g. DOGE, XRP)..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full sm:w-72 rounded-xl border border-white/[0.08] bg-[#07070a] px-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-[#00F5A0] focus:ring-1 focus:ring-[#00F5A0]/30 transition"
        />
      </div>

      {/* Setup Cards Grid */}
      <section className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
        {filtered.map((s, idx) => {
          const isLong = s.direction?.toLowerCase() === "long";
          const idToCopy = s.setup_id || `setup_${s.symbol}_${s.strategy}`;

          return (
            <Card
              key={`${s.symbol}-${s.strategy}-${idx}`}
              className="p-6 bg-[#0a0a0d] border border-white/[0.07] hover:border-white/20 transition-all duration-300 rounded-2xl flex flex-col justify-between shadow-xl hover:shadow-[0_20px_40px_rgba(0,0,0,0.8)] group"
            >
              <div>
                {/* Symbol & Direction Header */}
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <b className="text-xl font-black text-white group-hover:text-[#00F5A0] transition-colors">{s.symbol}</b>
                    <p className="text-xs text-slate-400 capitalize mt-0.5">
                      {s.strategy.replace(/_/g, " ")}
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider ${
                        isLong
                          ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30"
                          : "bg-[#FF3366]/15 text-[#FF3366] border border-[#FF3366]/30"
                      }`}
                    >
                      {isLong ? "BUY · LONG" : "SELL · SHORT"}
                    </span>
                    <span className="rounded-lg bg-white/[0.04] border border-white/[0.08] px-2.5 py-0.5 text-[11px] font-bold text-slate-300 font-mono">
                      {s.setup_quality_score?.toFixed(1) ?? "—"}
                    </span>
                  </div>
                </div>

                {/* Trade Execution Levels Box */}
                <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-[#060608] p-4 border border-white/[0.05] text-xs">
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Trigger Entry</span>
                    <p className="mt-0.5 font-black text-white text-sm font-mono">
                      ${money(s.trigger_price)}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Risk / Reward</span>
                    <p className="mt-0.5 font-black text-[#00D9F5] text-sm font-mono">
                      {s.risk_reward ? `${s.risk_reward.toFixed(2)} R:R` : "2.00 R:R"}
                    </p>
                  </div>

                  <div className="pt-2.5 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Profit Target (TP)</span>
                    <p className="mt-0.5 font-black text-[#00F5A0] text-sm font-mono">
                      ${money(s.hypothetical_target)}
                    </p>
                  </div>

                  <div className="pt-2.5 border-t border-white/[0.05]">
                    <span className="text-slate-500 text-[10px] uppercase font-bold tracking-wider">Stop Loss (SL)</span>
                    <p className="mt-0.5 font-black text-[#FF3366] text-sm font-mono">
                      ${money(s.hypothetical_stop)}
                    </p>
                  </div>
                </div>

                {/* Status & Expiry */}
                <div className="mt-3.5 flex items-center justify-between text-xs text-slate-400">
                  <span>
                    Status: <b className="text-slate-200 capitalize font-medium">{s.status.replace(/_/g, " ")}</b>
                  </span>
                  {s.expires_at && (
                    <span className="font-mono text-[11px]">
                      Exp: <b className="text-slate-300">{formatIST(s.expires_at)}</b>
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="mt-5 pt-4 border-t border-white/[0.06] flex items-center justify-between gap-3">
                <button
                  onClick={() => copySetup(idToCopy)}
                  className="cred-btn-secondary px-3 py-1.5 rounded-lg text-xs font-semibold"
                >
                  {copiedId === idToCopy ? "✓ Copied Setup ID" : "Copy Setup ID"}
                </button>

                <Link
                  href="/live"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#00F5A0] hover:bg-[#00d68c] px-4 py-1.5 text-xs font-black text-black transition-all shadow-[0_0_15px_rgba(0,245,160,0.3)]"
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
