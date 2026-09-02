"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Card } from "@/components/ui/card";
import { getApiUrl } from "@/lib/api";

type Setup = {
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
  const [error, setError] = useState("");
  useEffect(() => {
    fetch(`${getApiUrl()}/setups?limit=500`)
      .then((response) => {
        if (!response.ok) throw new Error(`setup request failed (${response.status})`);
        return response.json();
      })
      .then((data) => setRows(data.items ?? []))
      .catch((cause) => setError(String(cause)));
  }, []);
  const filtered = useMemo(
    () => rows.filter((row) => row.symbol.toLowerCase().includes(query.toLowerCase())),
    [query, rows],
  );
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">Phase 6 analysis</p>
      <h1 className="mt-1 text-2xl font-semibold">Deterministic setup monitor</h1>
      <p className="mt-1 text-sm font-medium text-amber-300">SIMULATED / NON-EXECUTABLE</p>
      <p className="text-sm text-slate-400">Hypothetical analytical setups only. No orders, sizing, or trade controls.</p>
      {error && <p className="mt-4 rounded-lg bg-red-950 p-3 text-red-300">{error}</p>}
      <Card className="mt-5 overflow-x-auto">
        <input className="mb-4 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" placeholder="Search symbol" value={query} onChange={(event) => setQuery(event.target.value)} />
        <table className="w-full min-w-[1250px] text-left text-sm">
          <thead className="text-xs uppercase text-slate-500"><tr><th className="py-2">Symbol</th><th>Opportunity</th><th>Strategy</th><th>Direction</th><th>Quality</th><th>Status</th><th>Entry zone</th><th>Trigger</th><th>SL</th><th>TP</th><th>R:R</th><th>Expires</th><th>Warnings</th></tr></thead>
          <tbody>{filtered.map((row) => <tr className="border-t border-slate-800" key={`${row.symbol}-${row.strategy}`}><td className="py-3"><Link className="text-cyan-300 hover:underline" href={`/setups/${encodeURIComponent(row.symbol)}`}>{row.symbol}</Link></td><td>{row.opportunity_score.toFixed(1)}</td><td>{row.strategy.replaceAll("_", " ")}</td><td className="uppercase">{row.direction}</td><td>{row.setup_quality_score.toFixed(1)}</td><td className="uppercase">{row.status.replaceAll("_", " ")}</td><td>{row.entry_zone ? `${row.entry_zone.low.toPrecision(6)}–${row.entry_zone.high.toPrecision(6)}` : "—"}</td><td>{row.trigger_price?.toPrecision(6) ?? "—"}</td><td>{row.hypothetical_stop?.toPrecision(6) ?? "—"}</td><td>{row.hypothetical_target?.toPrecision(6) ?? "—"}</td><td>{row.risk_reward?.toFixed(2) ?? "—"}</td><td>{row.expires_at ? new Date(row.expires_at).toLocaleTimeString() : "—"}</td><td>{row.warnings.length || "—"}</td></tr>)}</tbody>
        </table>
      </Card>
    </main>
  );
}
