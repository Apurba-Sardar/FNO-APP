import "./globals.css";
export const metadata = { title: "FNO Scanner", description: "Deterministic CoinDCX futures scanner" };
export default function Layout({ children }: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body>{children}</body></html>;
}

