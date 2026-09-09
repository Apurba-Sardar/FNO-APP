import "./globals.css";
import { AuthGuard } from "@/components/auth-guard";
import { Header } from "@/components/header";

export const metadata = {
  title: "FNO Scanner — Algorithmic Futures Suite",
  description: "Deterministic CoinDCX futures scanner & live trading manager",
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#050507] text-[#EDEDED] antialiased min-h-screen selection:bg-[#00F5A0]/25 selection:text-[#00F5A0]">
        <AuthGuard>
          <Header />
          <main className="relative z-10">{children}</main>
        </AuthGuard>
      </body>
    </html>
  );
}
