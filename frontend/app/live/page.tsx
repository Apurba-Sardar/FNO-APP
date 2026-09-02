"use client";

import { Card } from "@/components/ui/card";
import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
type Row = Record<string, any>;

export default function LivePage() {
  const [operatorToken, setOperatorToken] = useState("LIVE_OPERATOR_TOKEN_2026");
  const [emergencyToken, setEmergencyToken] = useState("LIVE_EMERGENCY_TOKEN_2026");
  const [status, setStatus] = useState<Row>({});
  const [account, setAccount] = useState<Row>({});
  const [positions, setPositions] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [setupId, setSetupId] = useState("");
  const [intent, setIntent] = useState<Row | null>(null);
  const [grant, setGrant] = useState("");
  const [message, setMessage] = useState("Live state active.");
  const headers = useCallback(() => ({ "Content-Type": "application/json", "x-live-operator-token": operatorToken }), [operatorToken]);

  const load = useCallback(async () => {
    try {
      const results = await Promise.all(["status", "account", "positions", "orders"].map(async path => {
        const response = await fetch(`${API}/live/${path}`, { headers: headers(), cache: "no-store" });
        if (!response.ok) throw new Error((await response.json()).detail ?? "Live API unavailable");
        return response.json();
      }));
      setStatus(results[0]); setAccount(results[1]); setPositions(results[2].items ?? []); setOrders(results[3].items ?? []); setMessage("Live state refreshed.");
    } catch (err: any) {
      setMessage(err.message ?? "Error loading state");
    }
  }, [headers]);

  useEffect(() => {
    load();
    const timer = setInterval(load, 10000);
    return () => clearInterval(timer);
  }, [load]);

  const command = async (path: string, body: Row, emergency = false) => {
    const requestHeaders = emergency ? { "Content-Type": "application/json", "x-live-emergency-token": emergencyToken } : headers();
    const response = await fetch(`${API}/live/${path}`, { method: "POST", headers: requestHeaders, body: JSON.stringify(body) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail ?? "Command rejected");
    return result;
  };
  const prepare = async () => { try { const result = await command("execute", { setup_id: setupId }); setIntent(result.execution); setGrant(result.confirmation_token ?? ""); setMessage(result.confirmation_token ? "Intent prepared. Review it, then confirm within 30 seconds." : "Stage 2 validation completed; no submission is permitted."); } catch (error) { setMessage(error instanceof Error ? error.message : "Rejected"); } };
  const confirm = async () => { if (!intent || !grant) return; try { await command("execute", { execution_request_id: intent.execution_request_id, confirmation_token: grant, confirmation_phrase: "EXECUTE REAL TRADE" }); setMessage("Order workflow submitted; refresh exchange state immediately."); setGrant(""); await load(); } catch (error) { setMessage(error instanceof Error ? error.message : "Rejected"); } };
  const stop = async () => { try { await command("emergency-stop", {}, true); setMessage("Emergency stop triggered. New entries are blocked; positions remain monitored."); await load(); } catch (error) { setMessage(error instanceof Error ? error.message : "Rejected"); } };
  const money = (value: unknown) => Number(value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 4 });

  return <main className="mx-auto max-w-7xl p-4 sm:p-6">
    <header className="rounded-2xl border-2 border-rose-500 bg-rose-500/10 p-5"><p className="text-xs font-bold uppercase tracking-[.3em] text-rose-300">Live Trading</p><h1 className="mt-1 text-3xl font-black text-rose-200">LIVE MODE — REAL MONEY & HOLDINGS</h1><p className="mt-2 text-sm text-slate-300">Real-time CoinDCX Futures account balances, open trades, and safety monitoring.</p></header>
    <section className="mt-4 grid gap-3 md:grid-cols-2"><Card><label className="text-xs uppercase text-slate-500">Operator token</label><input type="password" value={operatorToken} onChange={e => setOperatorToken(e.target.value)} className="mt-2 w-full rounded border border-slate-700 bg-slate-950 p-2"/><button onClick={() => load().catch(e => setMessage(e.message))} className="mt-3 rounded bg-slate-200 px-4 py-2 text-sm font-bold text-slate-950">Refresh Live State</button></Card><Card className="border-rose-500/40"><label className="text-xs uppercase text-rose-300">Emergency-role token</label><input type="password" value={emergencyToken} onChange={e => setEmergencyToken(e.target.value)} className="mt-2 w-full rounded border border-rose-700 bg-slate-950 p-2"/><button onClick={stop} className="mt-3 rounded bg-rose-600 px-4 py-2 text-sm font-black">STOP NEW TRADES</button></Card></section>
    <p className="mt-4 rounded-lg border border-slate-700 p-3 text-sm text-slate-300">{message}</p>
    <section className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4"><Card><small>Runtime</small><b className="mt-2 block uppercase">{status.runtime_state ?? "locked"}</b></Card><Card><small>Stage</small><b className="mt-2 block">{status.stage ?? 0} · {status.stage_name ?? "PAPER_ONLY"}</b></Card><Card><small>Emergency stop</small><b className="mt-2 block uppercase text-rose-300">{status.emergency_stop ?? "unknown"}</b></Card><Card><small>Auto execution</small><b className="mt-2 block">{status.auto_execution ? "ON" : "OFF"}</b></Card><Card><small>Account equity</small><b className="mt-2 block">${money(account.equity)} USDT</b></Card><Card><small>Available balance</small><b className="mt-2 block">${money(account.available_balance)} USDT</b></Card><Card><small>Locked margin</small><b className="mt-2 block">${money(account.locked_margin)} USDT</b></Card><Card><small>Open positions</small><b className="mt-2 block">{positions.length || (status.open_positions ?? 0)}</b></Card></section>
    <section className="mt-5"><Card><h2 className="font-semibold">Two-step setup approval</h2><p className="mt-1 text-xs text-slate-400">Only a setup ID is accepted. Quantity, leverage, entry, stop, and target are loaded and revalidated server-side.</p><div className="mt-3 flex gap-2"><input value={setupId} onChange={e => setSetupId(e.target.value)} placeholder="setup_id" className="min-w-0 flex-1 rounded border border-slate-700 bg-slate-950 p-2"/><button onClick={prepare} className="rounded border border-amber-400 px-4 text-amber-300">Prepare</button></div>{intent && <div className="mt-4 rounded border border-rose-500/40 p-4 text-sm"><div className="grid grid-cols-2 gap-2 md:grid-cols-4"><span>Pair<br/><b>{intent.symbol}</b></span><span>Direction<br/><b>{intent.direction}</b></span><span>Quantity<br/><b>{money(intent.quantity)}</b></span><span>Risk<br/><b>{money(intent.risk_amount)}</b></span><span>Entry<br/><b>{money(intent.expected_entry)}</b></span><span>Stop<br/><b>{money(intent.stop)}</b></span><span>Target<br/><b>{money(intent.target)}</b></span><span>Notional<br/><b>{money(intent.notional)}</b></span></div>{grant && <button onClick={confirm} className="mt-4 rounded bg-rose-600 px-4 py-2 font-black">EXECUTE REAL TRADE</button>}</div>}</Card></section>
    <section className="mt-5 grid gap-4 lg:grid-cols-2"><Card><h2 className="text-lg font-bold">Live positions & holdings ({positions.length})</h2>{positions.length ? positions.map(p => <div key={p.position_id} className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-4"><div className="flex justify-between items-center"><b className="text-base">{p.pair} · <span className={p.direction === "long" ? "text-emerald-400" : "text-rose-400"}>{String(p.direction).toUpperCase()}</span></b><span className={p.unrealized_pnl >= 0 ? "font-bold text-emerald-400" : "font-bold text-rose-400"}>{p.unrealized_pnl >= 0 ? "+" : ""}{money(p.unrealized_pnl)} USDT</span></div><p className="mt-1 text-xs font-semibold uppercase text-slate-400">{p.protection_status === "protected" ? "Protected" : "Live Position"} · {p.leverage}x {p.margin_mode}</p><div className="mt-2 grid grid-cols-2 gap-2 text-sm text-slate-300"><span>Quantity: <b>{money(p.quantity)}</b></span><span>Margin: <b>${money(p.margin)}</b></span><span>Entry: <b>${money(p.average_price)}</b></span><span>Mark: <b>${money(p.mark_price)}</b></span>{p.target && <span>Target: <b>${money(p.target)}</b></span>}{p.stop && <span>Stop: <b>${money(p.stop)}</b></span>}</div></div>) : <p className="mt-3 text-sm text-slate-500">No active live positions.</p>}</Card><Card><h2 className="text-lg font-bold">Execution activity & orders</h2>{orders.length ? orders.map(o => <div key={o.order_id} className="mt-3 rounded-lg border border-slate-800 bg-slate-950 p-3 text-sm"><b className="text-slate-200">{o.pair} · {o.status}</b><p className="text-slate-400">Filled {money(o.filled_quantity)} / {money(o.requested_quantity)}</p></div>) : <p className="mt-3 text-sm text-slate-500">No active orders.</p>}</Card></section>
  </main>;
}
