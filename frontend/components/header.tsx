"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { logout } from "./auth-guard";
import { formatISTTime } from "@/lib/format";

const navigation = [
  ["Command Center", "/"],
  ["Market Scanner", "/scanner"],
  ["Opportunities", "/opportunities"],
  ["Strategy Setups", "/setups"],
  ["Risk Controls", "/risk"],
  ["Paper Trading", "/paper"],
  ["Backtests", "/backtests"],
  ["Live Depth", "/market-data"],
] as const;

export function Header() {
  const pathname = usePathname();
  const [currentIST, setCurrentIST] = useState<string>("");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    const updateTime = () => setCurrentIST(formatISTTime(new Date()));
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  if (pathname === "/login") return null;

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/85 backdrop-blur-xl shadow-xl shadow-black/20">
      <div className="mx-auto max-w-[1600px] px-3 sm:px-6">
        <div className="flex h-14 items-center justify-between gap-3">
          {/* Logo & Brand */}
          <Link href="/" className="flex shrink-0 items-center gap-2.5 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-500 to-cyan-400 font-black text-slate-950 shadow-lg shadow-cyan-500/20 group-hover:scale-105 transition">
              F
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-black tracking-wider text-white leading-none">
                FNO <span className="text-cyan-400 font-extrabold text-xs">SUITE</span>
              </span>
              <span className="text-[10px] text-slate-400 font-medium tracking-tight">Algorithmic Futures</span>
            </div>
          </Link>

          {/* Desktop Navigation */}
          <nav className="hidden min-w-0 flex-1 items-center justify-center gap-1 overflow-x-auto lg:flex">
            {navigation.map(([label, href]) => {
              const active = href === "/" ? pathname === href : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    active
                      ? "bg-slate-800/90 text-white shadow-sm border border-slate-700/60"
                      : "text-slate-400 hover:bg-slate-900/60 hover:text-slate-200"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>

          {/* Right Controls: IST Clock, Live Mode, Logout */}
          <div className="flex shrink-0 items-center gap-3 text-xs">
            {/* Live IST Clock */}
            {currentIST && (
              <div className="hidden sm:flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-slate-300 font-mono text-[11px] shadow-inner">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>{currentIST}</span>
              </div>
            )}

            {/* Live Trading Button */}
            <Link
              href="/live"
              className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-bold transition shadow-sm ${
                pathname.startsWith("/live")
                  ? "border-rose-500 bg-rose-600 text-white shadow-rose-600/30"
                  : "border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 hover:border-rose-500/60"
              }`}
            >
              <span className="h-2 w-2 rounded-full bg-rose-400 animate-ping"></span>
              Live Trading
            </Link>

            {/* Logout Button */}
            <button
              onClick={logout}
              className="rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-1.5 font-semibold text-slate-400 hover:bg-slate-800 hover:text-white transition text-xs"
            >
              Sign out
            </button>

            {/* Mobile menu trigger */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden rounded-lg border border-slate-800 p-1.5 text-slate-400 hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={mobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"} />
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <nav className="flex flex-col gap-1 py-3 border-t border-slate-800/80 text-xs lg:hidden">
            {navigation.map(([label, href]) => {
              const active = href === "/" ? pathname === href : pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`rounded-lg px-3 py-2 font-medium ${
                    active ? "bg-slate-800 text-white font-bold" : "text-slate-400 hover:bg-slate-900 hover:text-white"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        )}
      </div>
    </header>
  );
}
