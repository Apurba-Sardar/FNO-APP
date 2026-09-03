"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "./auth-guard";

const navigation = [
  ["Overview", "/"],
  ["Scanner", "/scanner"],
  ["Opportunities", "/opportunities"],
  ["Setups", "/setups"],
  ["Risk", "/risk"],
  ["Paper", "/paper"],
  ["Backtests", "/backtests"],
  ["Market data", "/market-data"],
] as const;

export function Header() {
  const pathname = usePathname();

  if (pathname === "/login") return null;

  return (
    <div className="sticky top-0 z-50 border-b border-slate-800/90 bg-slate-950/90 shadow-lg shadow-black/10 backdrop-blur-xl">
      <div className="mx-auto max-w-[1600px] px-3 sm:px-5">
        <div className="flex h-12 items-center justify-between gap-3">
          <Link href="/" className="flex shrink-0 items-center gap-2 font-black tracking-wider text-cyan-300">
            <span className="grid h-7 w-7 place-items-center rounded-lg bg-cyan-400 text-xs text-slate-950 shadow-lg shadow-cyan-500/20">F</span>
            <span className="text-sm">FNO</span>
          </Link>
          <div className="hidden min-w-0 flex-1 items-center gap-1 overflow-x-auto lg:flex">
            {navigation.map(([label, href]) => {
              const active = href === "/" ? pathname === href : pathname.startsWith(href);
              return <Link key={href} href={href} className={`whitespace-nowrap rounded-md px-2.5 py-1.5 ${active ? "bg-slate-800 font-semibold text-white" : "text-slate-400 hover:bg-slate-900 hover:text-slate-100"}`}>{label}</Link>;
            })}
          </div>
          <div className="flex shrink-0 items-center gap-2 text-xs">
            <Link href="/live" className={`rounded-md border px-2.5 py-1.5 font-bold ${pathname.startsWith("/live") ? "border-rose-400/60 bg-rose-500/20 text-rose-200" : "border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20"}`}>Live</Link>
            <span className="hidden rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 font-semibold text-emerald-400 sm:inline-block">
              ● Connected
            </span>
          <button
            onClick={logout}
              className="rounded-md bg-slate-800 px-2.5 py-1.5 font-semibold text-slate-300 hover:bg-slate-700 hover:text-white"
          >
              Log out
          </button>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto pb-2 text-xs lg:hidden">
          {navigation.map(([label, href]) => {
            const active = href === "/" ? pathname === href : pathname.startsWith(href);
            return <Link key={href} href={href} className={`whitespace-nowrap rounded-md px-2.5 py-1.5 ${active ? "bg-slate-800 font-semibold text-white" : "text-slate-400 hover:bg-slate-900 hover:text-white"}`}>{label}</Link>;
          })}
        </nav>
      </div>
    </div>
  );
}
