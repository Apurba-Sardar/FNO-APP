"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { logout } from "./auth-guard";

const navItems = [
  {
    label: "Live Scalp",
    href: "/live",
    badge: "LIVE",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    label: "Scanner",
    href: "/scanner",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    label: "PnL Logs",
    href: "/pnl",
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    label: "Kill Switch",
    href: "/settings",
    icon: (
      <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M18.364 5.636a9 9 0 010 12.728m0 0l-2.829-2.829m2.829 2.829L21 21M15.536 8.464a5 5 0 010 7.072m0 0l-2.829-2.829m-4.243 2.829a4.978 4.978 0 01-1.414-2.83m-1.414 5.658a9 9 0 01-2.167-9.238m7.824-2.167a1 1 0 111.414 1.414m-1.414-1.414L3 3m8.293 8.293l1.414 1.414" />
      </svg>
    ),
  },
];

const drawerNavigation = [
  ["Command Center", "/"],
  ["Market Scanner", "/scanner"],
  ["Opportunities", "/opportunities"],
  ["Strategy Setups", "/setups"],
  ["Risk Controls", "/risk"],
  ["Paper Trading", "/paper"],
  ["Backtests", "/backtests"],
  ["Live Depth", "/market-data"],
  ["PnL & Logs", "/pnl"],
  ["Settings & Master Switch", "/settings"],
] as const;

export function MobileNav() {
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (pathname === "/login") return null;

  return (
    <>
      {/* Fixed Luxury Mobile Bottom Bar */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 lg:hidden border-t border-white/[0.09] bg-[#07070a]/95 backdrop-blur-3xl px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-12px_40px_rgba(0,0,0,0.95)]">
        <div className="grid grid-cols-5 items-center justify-around gap-1 max-w-md mx-auto">
          {navItems.map(item => {
            const active = item.href === "/" ? pathname === item.href : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative flex flex-col items-center justify-center py-1.5 px-1 rounded-xl transition-all duration-200 active:scale-95 ${
                  active
                    ? "text-[#00F5A0] font-black bg-white/[0.05]"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                {/* Active Indicator Top Glow */}
                {active && (
                  <span className="absolute -top-2 h-1 w-6 rounded-full bg-[#00F5A0] shadow-[0_0_12px_#00F5A0]" />
                )}

                <div className="relative">
                  {item.icon}
                  {item.badge && (
                    <span className="absolute -top-1.5 -right-2 flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-500 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                    </span>
                  )}
                </div>
                <span className="text-[10px] mt-1 tracking-tight truncate font-semibold">
                  {item.label}
                </span>
              </Link>
            );
          })}

          {/* More Drawer Trigger */}
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="flex flex-col items-center justify-center py-1.5 px-1 rounded-xl text-zinc-400 hover:text-white transition-all active:scale-95 cursor-pointer"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.2" d="M4 6h16M4 12h16m-7 6h7" />
            </svg>
            <span className="text-[10px] mt-1 tracking-tight font-semibold">Menu</span>
          </button>
        </div>
      </nav>

      {/* Mobile Drawer Modal */}
      {drawerOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex flex-col justify-end bg-black/80 backdrop-blur-md">
          <div
            className="absolute inset-0"
            onClick={() => setDrawerOpen(false)}
          />
          <div className="relative z-10 rounded-t-3xl border-t border-white/10 bg-[#0a0a0e] p-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-2xl max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
              <div className="flex items-center gap-2">
                <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-[#00F5A0] to-[#00D9F5] flex items-center justify-center text-slate-950 font-black text-xs">
                  F
                </div>
                <span className="text-sm font-black text-white">FNO Suite Navigation</span>
              </div>
              <button
                type="button"
                onClick={() => setDrawerOpen(false)}
                className="h-8 w-8 rounded-full bg-white/[0.05] hover:bg-white/[0.1] text-zinc-400 hover:text-white flex items-center justify-center text-xs font-bold cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="mt-3 grid grid-cols-2 gap-2">
              {drawerNavigation.map(([label, href]) => {
                const active = href === "/" ? pathname === href : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    onClick={() => setDrawerOpen(false)}
                    className={`rounded-xl px-3 py-2.5 text-xs font-bold transition flex items-center justify-between ${
                      active
                        ? "bg-[#00F5A0]/15 text-[#00F5A0] border border-[#00F5A0]/30 shadow-[0_0_15px_rgba(0,245,160,0.15)]"
                        : "bg-white/[0.03] text-zinc-300 border border-white/[0.06] hover:bg-white/[0.06]"
                    }`}
                  >
                    <span className="truncate">{label}</span>
                    {active && <span className="h-1.5 w-1.5 rounded-full bg-[#00F5A0]" />}
                  </Link>
                );
              })}
            </div>

            <div className="mt-4 pt-3 border-t border-white/[0.08] flex items-center justify-between">
              <Link
                href="/settings"
                onClick={() => setDrawerOpen(false)}
                className="text-xs font-bold text-amber-400 hover:text-amber-300 flex items-center gap-1.5"
              >
                <span>⚠️ Emergency Master Switch</span>
              </Link>
              <button
                type="button"
                onClick={() => {
                  setDrawerOpen(false);
                  logout();
                }}
                className="rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 px-3 py-1.5 text-xs font-bold hover:bg-rose-500/25 cursor-pointer"
              >
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
