import "./globals.css";
import Link from "next/link";
export const metadata = { title: "FNO Scanner", description: "Deterministic CoinDCX futures scanner" };
export default function Layout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body><div className="border-b border-amber-500/20 bg-amber-500/5"><div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2 text-xs"><div className="flex gap-4"><Link href="/" className="font-semibold tracking-wide text-slate-200">FNO SCANNER</Link><Link href="/live" className="text-rose-300">Live controls</Link></div><span className="rounded-full border border-amber-400/40 px-3 py-1 font-bold tracking-[.16em] text-amber-300">DEFAULT: PAPER · LIVE FAIL-CLOSED</span></div></div>{children}</body></html>;
}
