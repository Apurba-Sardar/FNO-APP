import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthGuard } from "@/components/auth-guard";
import { Header } from "@/components/header";
import { MobileNav } from "@/components/mobile-nav";

export const metadata: Metadata = {
  title: "FNO Scanner — Algorithmic Futures Suite",
  description: "Deterministic CoinDCX futures scanner & live trading manager",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#050507",
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#050507] text-[#EDEDED] antialiased min-h-screen selection:bg-[#00F5A0]/25 selection:text-[#00F5A0]">
        <AuthGuard>
          <Header />
          <main className="relative z-10 pb-20 lg:pb-0">{children}</main>
          <MobileNav />
        </AuthGuard>
      </body>
    </html>
  );
}
