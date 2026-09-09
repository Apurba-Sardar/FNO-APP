"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

type Account = { account_equity: number | null; available_balance: number | null; consecutive_losses: number; open_positions: unknown[] };
type State = { account: Account; daily_pnl: number; daily_loss_percent: number; total_exposure: number; exposure_percent: number; trading_lock: string; block_reasons: string[] };
type Config = { risk_per_trade_percent: number; max_daily_loss_percent: number; max_consecutive_losses: number; max_open_positions: number; max_total_exposure_percent: number };
type Decision = { symbol: string; strategy: string; direction: string; allowed: boolean; status: string; risk_amount: number; position_quantity: number; position_notional: number; maximum_loss: number; estimated_rr: number; rejection_reasons: string[] };

const show = (value: number | null | undefined, suffix = "") =>
  value == null ? "Unavailable" : `${value.toLocaleString(undefined, { maximumFractionDigits: 4 })}${suffix}`;

export default function RiskCenterPage() {
  const [state, setState] = useState<State | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const api = getApiUrl();
    Promise.all([
      fetch(`${api}/risk/status`).then((r) => r.json()),
      fetch(`${api}/risk/config`).then((r) => r.json()),
      fetch(`${api}/risk/decisions?limit=500`).then((r) => r.json()),
    ])
      .then(([status, settings, rows]) => {
        setState(status.state);
        setConfig(settings);
        setDecisions(rows.items ?? []);
      })
      .catch((cause) => setError(String(cause)));
  }, []);

  const isLockOpen = state?.trading_lock === "open";

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
                <span>🛡️</span> Portfolio Risk Engine
              </span>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                Real-Time Margin & Position Guard
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                Capital Shield & Risk Center
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              Autonomous capital protection, position sizing quotas, exposure limits, and deterministic safety lock authority.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-2 rounded-2xl px-5 py-2.5 text-xs font-black uppercase tracking-wider border shadow-lg ${
                isLockOpen
                  ? "bg-[#00F5A0]/10 text-[#00F5A0] border-[#00F5A0]/30 shadow-[0_0_20px_rgba(0,245,160,0.2)]"
                  : "bg-[#FF3366]/10 text-[#FF3366] border-[#FF3366]/30 shadow-[0_0_20px_rgba(255,51,102,0.2)]"
              }`}
            >
              <span className={`h-2.5 w-2.5 rounded-full ${isLockOpen ? "bg-[#00F5A0] animate-pulse" : "bg-[#FF3366]"}`}></span>
              Trading Lock: {state?.trading_lock ?? "Connecting..."}
            </span>
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs font-semibold text-rose-300 shadow-lg">
          ⚠️ {error}
        </div>
      )}

      {/* Metric Cards Grid - CRED Sculpted Obsidian */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Account Equity</p>
          <p className="mt-2 text-2xl font-black text-white tracking-tight font-mono">
            {show(state?.account.account_equity)}
          </p>
          <span className="mt-1 block text-[11px] text-slate-400">Total portfolio valuation</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Available Balance</p>
          <p className="mt-2 text-2xl font-black text-[#00F5A0] tracking-tight font-mono">
            {show(state?.account.available_balance)}
          </p>
          <span className="mt-1 block text-[11px] text-slate-400">Free unallocated margin</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Risk Per Trade</p>
          <p className="mt-2 text-2xl font-black text-[#00D9F5] tracking-tight font-mono">
            {show(config?.risk_per_trade_percent, "%")}
          </p>
          <span className="mt-1 block text-[11px] text-slate-400">Strict notional stop allocation</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Today&apos;s P&amp;L / Loss</p>
          <p className="mt-2 text-2xl font-black text-white tracking-tight font-mono">
            {show(state?.daily_pnl)} · {show(state?.daily_loss_percent, "%")}
          </p>
          <span className="mt-1 block text-[11px] text-slate-500 font-mono">Limit: {show(config?.max_daily_loss_percent, "%")}</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Consecutive Losses</p>
          <p className="mt-2 text-2xl font-black text-white tracking-tight font-mono">
            {show(state?.account.consecutive_losses)} <span className="text-sm font-normal text-slate-500">/ {show(config?.max_consecutive_losses)} max</span>
          </p>
          <span className="mt-1 block text-[11px] text-slate-400">Loss streak threshold</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Open Positions</p>
          <p className="mt-2 text-2xl font-black text-[#00F5A0] tracking-tight font-mono">
            {state?.account.open_positions.length ?? 0} <span className="text-sm font-normal text-slate-500">/ {config?.max_open_positions ?? "—"} max</span>
          </p>
          <span className="mt-1 block text-[11px] text-slate-400">Concurrent active trades</span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Total Exposure</p>
          <p className="mt-2 text-2xl font-black text-white tracking-tight font-mono">
            {show(state?.total_exposure)}
          </p>
          <span className="mt-1 block text-[11px] text-slate-400 font-mono">
            {show(state?.exposure_percent, "%")} / {show(config?.max_total_exposure_percent, "%")} limit
          </span>
        </Card>

        <Card className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
          <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Block Reasons</p>
          {state?.block_reasons.length ? (
            <div className="mt-2 space-y-1">
              {state.block_reasons.map((reason) => (
                <p className="text-xs font-bold text-[#FF3366]" key={reason}>• {reason}</p>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-xl font-bold text-[#00F5A0]">Clean / None</p>
          )}
        </Card>
      </section>

      {/* Risk Decisions Table */}
      <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-lg font-black text-white tracking-tight">Autonomous Risk Decisions Log</h2>
            <p className="text-xs text-slate-400">Historical algorithmic approvals, sizing determinations, and rejected setups.</p>
          </div>
          <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-xs text-slate-400 font-mono">
            {decisions.length} Decisions Logged
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead>
              <tr className="border-b border-white/[0.07] text-[10px] font-black uppercase tracking-[0.15em] text-slate-500">
                <th className="py-3 px-3">Symbol</th>
                <th className="py-3 px-3">Strategy</th>
                <th className="py-3 px-3">Direction</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3 text-right">Risk Budget</th>
                <th className="py-3 px-3 text-right">Quantity</th>
                <th className="py-3 px-3 text-right">Notional</th>
                <th className="py-3 px-3 text-right">Max Loss</th>
                <th className="py-3 px-3 text-right">R:R</th>
                <th className="py-3 px-3 text-center">Rejections</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.04]">
              {decisions.map((row) => (
                <tr className="hover:bg-white/[0.02] transition-colors" key={`${row.symbol}-${row.strategy}`}>
                  <td className="py-3 px-3 font-bold text-white">
                    <Link className="text-[#00D9F5] hover:text-white transition-colors" href={`/risk/${encodeURIComponent(row.symbol)}`}>
                      {row.symbol}
                    </Link>
                  </td>
                  <td className="py-3 px-3 text-slate-300 capitalize">{row.strategy.replaceAll("_", " ")}</td>
                  <td className="py-3 px-3">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase tracking-wider ${
                      row.direction.toLowerCase() === "long" || row.direction.toLowerCase() === "buy"
                        ? "bg-[#00F5A0]/10 text-[#00F5A0] border border-[#00F5A0]/30"
                        : "bg-[#FF3366]/10 text-[#FF3366] border border-[#FF3366]/30"
                    }`}>
                      {row.direction}
                    </span>
                  </td>
                  <td className="py-3 px-3">
                    <span className={`font-bold ${row.allowed ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                      {row.status.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-slate-300">{show(row.risk_amount)}</td>
                  <td className="py-3 px-3 text-right font-mono text-slate-300">{show(row.position_quantity)}</td>
                  <td className="py-3 px-3 text-right font-mono text-slate-300">${show(row.position_notional)}</td>
                  <td className="py-3 px-3 text-right font-mono text-[#FF3366]">${show(row.maximum_loss)}</td>
                  <td className="py-3 px-3 text-right font-mono text-[#00D9F5]">{show(row.estimated_rr)}</td>
                  <td className="py-3 px-3 text-center font-mono">
                    {row.rejection_reasons.length > 0 ? (
                      <span className="text-[#FF3366] font-bold">{row.rejection_reasons.length}</span>
                    ) : (
                      <span className="text-slate-600">0</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </main>
  );
}
