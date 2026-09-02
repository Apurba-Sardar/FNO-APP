"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout } from "./auth-guard";

export function Header() {
  const pathname = usePathname();

  if (pathname === "/login") return null;

  return (
    <div className="border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2.5 text-xs">
        <div className="flex items-center gap-6">
          <Link href="/" className="font-black tracking-wider text-cyan-400 text-sm">
            FNO SCANNER
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/" className={`transition ${pathname === "/" ? "font-bold text-white" : "text-slate-400 hover:text-white"}`}>
              Overview
            </Link>
            <Link href="/live" className={`transition ${pathname === "/live" ? "font-bold text-rose-300" : "text-rose-400/80 hover:text-rose-300"}`}>
              Live Trading
            </Link>
            <Link href="/scanner" className={`transition ${pathname === "/scanner" ? "font-bold text-white" : "text-slate-400 hover:text-white"}`}>
              Scanner
            </Link>
            <Link href="/opportunities" className={`transition ${pathname === "/opportunities" ? "font-bold text-white" : "text-slate-400 hover:text-white"}`}>
              Opportunities
            </Link>
            <Link href="/setups" className={`transition ${pathname === "/setups" ? "font-bold text-white" : "text-slate-400 hover:text-white"}`}>
              Setups
            </Link>
            <Link href="/risk" className={`transition ${pathname === "/risk" ? "font-bold text-white" : "text-slate-400 hover:text-white"}`}>
              Risk
            </Link>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="hidden sm:inline-block rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 font-bold text-emerald-400">
            Authenticated User
          </span>
          <button
            onClick={logout}
            className="rounded bg-slate-800 px-3 py-1 font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition"
          >
            Log out 🚪
          </button>
        </div>
      </div>
    </div>
  );
}
