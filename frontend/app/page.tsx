import { Card } from "@/components/ui/card";
import Link from "next/link";

const sections = ["Scanner", "Ranked opportunities", "Active positions", "Trade history", "Strategy statistics", "Risk status", "System health"];
export default function Home() {
  return <main className="mx-auto max-w-7xl p-4 sm:p-6">
    <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div><p className="text-xs font-semibold uppercase tracking-[.2em] text-cyan-400">CoinDCX Futures</p><h1 className="text-2xl font-semibold">Deterministic opportunity scanner</h1></div>
      <span className="w-fit rounded-full border border-amber-500/40 bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-300">PAPER SIMULATION · PHASE 9</span>
    </header>
    <section className="grid gap-4 sm:grid-cols-3">
      <Card><p className="text-sm text-slate-400">Trading mode</p><p className="mt-2 text-xl font-semibold">Paper only</p></Card>
      <Card><p className="text-sm text-slate-400">Risk state</p><p className="mt-2 text-xl font-semibold text-emerald-400">Protected</p></Card>
      <Card><p className="text-sm text-slate-400">Live execution</p><p className="mt-2 text-xl font-semibold text-slate-400">Not implemented</p></Card>
    </section>
    <section className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {sections.map((section) => <Card key={section}><h2 className="font-medium">{section}</h2><p className="mt-2 text-sm text-slate-400">Phase 1 foundation ready for API-backed data.</p></Card>)}
    </section>
    <div className="mt-6 flex flex-wrap gap-3"><Link className="inline-flex rounded-lg bg-amber-400 px-4 py-2 text-sm font-semibold text-slate-950" href="/paper">Paper Trading</Link><Link className="inline-flex rounded-lg border border-slate-700 px-4 py-2 text-sm" href="/backtests">Backtesting Lab</Link><Link className="inline-flex rounded-lg border border-slate-700 px-4 py-2 text-sm" href="/risk">Risk Center</Link><Link className="inline-flex rounded-lg border border-slate-700 px-4 py-2 text-sm" href="/setups">Strategy setups</Link><Link className="inline-flex rounded-lg border border-slate-700 px-4 py-2 text-sm" href="/opportunities">Ranked opportunities</Link><Link className="inline-flex rounded-lg border border-slate-700 px-4 py-2 text-sm" href="/scanner">All-market scanner</Link><Link className="inline-flex rounded-lg border border-slate-700 px-4 py-2 text-sm" href="/market-data">Market data</Link></div>
  </main>;
}
