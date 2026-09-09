"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card } from "@/components/ui/card";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
type Check = { name: string; passed: boolean; value: unknown; threshold: unknown; severity: string; explanation: string };
type Decision = {
  strategy: string;
  direction: string;
  allowed: boolean;
  status: string;
  risk_amount: number;
  risk_percent: number;
  position_quantity: number;
  position_notional: number;
  estimated_leverage: number;
  required_margin: number;
  estimated_fees: number;
  estimated_slippage_cost: number;
  stop_loss_risk: number;
  maximum_loss: number;
  estimated_reward: number;
  estimated_rr: number;
  rejection_reasons: string[];
  warnings: string[];
  checks: Check[];
};
type Setup = { hypothetical_entry: number | null; hypothetical_stop: number | null; hypothetical_target: number | null; status: string };

const show = (value: unknown) =>
  typeof value === "number"
    ? value.toLocaleString(undefined, { maximumFractionDigits: 6 })
    : value == null
    ? "—"
    : Array.isArray(value)
    ? value.join("–")
    : String(value);

export default function RiskDetailPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(params.symbol);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [setups, setSetups] = useState<Record<string, Setup>>({});
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      fetch(`${API}/api/v1/risk/check/${encodeURIComponent(symbol)}`).then((r) => {
        if (!r.ok) throw new Error(`risk request failed (${r.status})`);
        return r.json();
      }),
      fetch(`${API}/api/v1/setups/${encodeURIComponent(symbol)}`).then((r) => r.json()),
    ])
      .then(([risk, setup]) => {
        setDecisions(risk.decisions);
        setSetups(setup.results ?? {});
        setSelected(Object.keys(risk.decisions)[0] ?? "");
      })
      .catch((cause) => setError(String(cause)));
  }, [symbol]);

  const decision = decisions[selected];
  const setup = setups[selected];

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
              <Link
                href="/risk"
                className="cred-btn-secondary px-3 py-1 rounded-lg text-xs font-semibold text-slate-300"
              >
                ← Back to Risk Center
              </Link>
              <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3 py-1 text-[11px] text-slate-300 font-mono">
                Hypothetical Guardrail Evaluation
              </span>
            </div>
            <h1 className="mt-3 text-2xl sm:text-4xl font-black tracking-tight text-white flex items-center gap-2">
              <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
                {symbol} Risk Audit
              </span>
            </h1>
            <p className="mt-1.5 text-xs sm:text-sm text-slate-400 font-normal max-w-2xl leading-relaxed">
              In-depth structural breakdown of margin requirements, stop exposure, and deterministic safety checks for {symbol}.
            </p>
          </div>
        </div>
      </header>

      {error && (
        <div className="rounded-2xl border border-rose-500/40 bg-rose-950/20 p-4 text-xs font-semibold text-rose-300 shadow-lg">
          ⚠️ {error}
        </div>
      )}

      {/* Strategy selector tabs */}
      <div className="flex flex-wrap gap-2">
        {Object.keys(decisions).map((name) => (
          <button
            className={`rounded-xl px-4 py-2 text-xs font-bold transition-all duration-200 ${
              name === selected
                ? "bg-[#00D9F5] text-black shadow-[0_0_15px_rgba(0,217,245,0.3)]"
                : "bg-[#0a0a0d] border border-white/[0.07] text-slate-400 hover:text-white"
            }`}
            key={name}
            onClick={() => setSelected(name)}
          >
            {name.replaceAll("_", " ")}
          </button>
        ))}
      </div>

      {decision ? (
        <div className="space-y-6">
          {/* Decision Status Banner */}
          <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">Autonomous Evaluation</p>
                <p
                  className={`mt-1 text-2xl font-black uppercase tracking-tight ${
                    decision.allowed ? "text-[#00F5A0]" : "text-[#FF3366]"
                  }`}
                >
                  {decision.status.replaceAll("_", " ")}
                </p>
              </div>
              <div className="text-right">
                <span className="rounded-full bg-white/[0.04] border border-white/[0.08] px-3.5 py-1 text-xs font-bold text-slate-300 uppercase">
                  {decision.direction.toUpperCase()} · {decision.strategy.replaceAll("_", " ")}
                </span>
              </div>
            </div>
          </Card>

          {/* Metric cards grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["Hypothetical Entry", setup?.hypothetical_entry],
              ["Hypothetical Stop", setup?.hypothetical_stop],
              ["Hypothetical Target", setup?.hypothetical_target],
              ["Structural R:R", decision.estimated_rr],
              ["Risk Budget", decision.risk_amount],
              ["Calculated Quantity", decision.position_quantity],
              ["Total Notional", decision.position_notional],
              ["Maximum Loss Cap", decision.maximum_loss],
              ["Stop Loss Risk", decision.stop_loss_risk],
              ["Estimated Fees", decision.estimated_fees],
              ["Slippage Cost", decision.estimated_slippage_cost],
              ["Estimated Reward", decision.estimated_reward],
              ["Required Margin", decision.required_margin],
              ["Required Leverage", decision.estimated_leverage],
            ].map(([label, value]) => (
              <Card key={String(label)} className="p-5 rounded-2xl border border-white/[0.07] bg-[#0a0a0d] shadow-xl">
                <p className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-500">{label}</p>
                <p className="mt-2 text-xl font-black text-white font-mono tracking-tight">{show(value)}</p>
              </Card>
            ))}
          </div>

          {/* Risk checks grid */}
          <Card className="p-6 rounded-3xl border border-white/[0.07] bg-[#0a0a0d] shadow-2xl">
            <h2 className="text-base font-black text-white tracking-tight mb-4">Guardrail Safety Checks</h2>
            <div className="grid gap-3 lg:grid-cols-2">
              {decision.checks.map((check) => (
                <div
                  className="rounded-2xl border border-white/[0.05] bg-[#060608] p-4 text-xs"
                  key={check.name}
                >
                  <p className={`font-bold text-sm ${check.passed ? "text-[#00F5A0]" : "text-[#FF3366]"}`}>
                    {check.passed ? "✓ Passed" : "✕ Failed"} · {check.name.replaceAll("_", " ")}
                  </p>
                  <p className="text-slate-400 font-mono mt-1">
                    Value: <b className="text-white">{show(check.value)}</b> · Threshold: <b className="text-slate-300">{show(check.threshold)}</b>
                  </p>
                  <p className="mt-1 text-slate-500">{check.explanation}</p>
                </div>
              ))}
            </div>
          </Card>

          {decision.rejection_reasons.length > 0 && (
            <Card className="p-6 rounded-3xl border border-rose-500/30 bg-rose-950/20 shadow-2xl">
              <h2 className="text-base font-black text-[#FF3366] tracking-tight mb-3">Rejection Reasons</h2>
              <div className="space-y-1.5 text-xs text-rose-200">
                {decision.rejection_reasons.map((reason) => (
                  <p key={reason}>✕ {reason}</p>
                ))}
              </div>
            </Card>
          )}
        </div>
      ) : (
        <Card className="p-12 text-center text-slate-500 text-sm rounded-3xl border border-white/[0.07] bg-[#0a0a0d]">
          Loading risk audit telemetry...
        </Card>
      )}
    </main>
  );
}
