import "./globals.css";
import { AuthGuard } from "@/components/auth-guard";
import { Header } from "@/components/header";

export const metadata = {
  title: "FNO Scanner — Algorithmic Futures Suite",
  description: "Deterministic CoinDCX futures scanner & live trading manager",
};

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased min-h-screen">
        <AuthGuard>
          <Header />
          {children}
        </AuthGuard>
      </body>
    </html>
  );
}
