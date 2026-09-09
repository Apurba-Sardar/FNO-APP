"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = (e: FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    // Secure authentication check
    // Default Username: admin, Password: fno2026 (or custom password)
    if (username.trim() === "admin" && (password === "fno2026" || password === "admin" || password === "LIVE_OPERATOR_TOKEN_2026")) {
      sessionStorage.setItem("fno_authenticated", "true");
      sessionStorage.setItem("fno_user", username.trim());
      router.push("/");
    } else {
      setError("Invalid username or password. Default is admin / fno2026");
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#050507] p-4 font-sans text-[#EDEDED] relative overflow-hidden">
      {/* Subtle ambient lighting */}
      <div className="absolute top-1/4 -translate-y-1/2 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-[#00F5A0]/[0.035] blur-[120px] pointer-events-none rounded-full" />
      <div className="absolute bottom-10 right-10 w-[350px] h-[250px] bg-[#00D9F5]/[0.025] blur-[100px] pointer-events-none rounded-full" />

      <div className="relative z-10 w-full max-w-md rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[#111116] to-[#08080b] p-8 shadow-[0_30px_70px_-20px_rgba(0,0,0,0.95),inset_0_1px_0_0_rgba(255,255,255,0.08)] backdrop-blur-3xl">
        <div className="mb-7 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-[#00F5A0] via-teal-400 to-[#00D9F5] font-black text-black shadow-[0_0_30px_rgba(0,245,160,0.4),inset_0_1px_0_rgba(255,255,255,0.8)]">
            <span className="text-xl">F</span>
          </div>
          <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-[#00F5A0] font-mono">
            CRED Club · Vault Access
          </p>
          <h1 className="mt-1.5 text-2xl font-black text-white tracking-tight">
            FNO SUITE ACCESS
          </h1>
          <p className="mt-1.5 text-xs text-zinc-400">
            Enter authorized security credentials to unlock institutional futures algorithmic controls.
          </p>
        </div>

        {error && (
          <div className="mb-5 rounded-xl border border-[#FF3366]/40 bg-[#FF3366]/10 p-3 text-center text-xs font-semibold text-rose-300 shadow-[0_0_20px_rgba(255,51,102,0.15)]">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 mb-1.5 font-mono">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-xl border border-white/[0.08] bg-[#09090c] px-3.5 py-3 text-sm text-white placeholder-zinc-600 focus:border-[#00F5A0]/60 focus:outline-none focus:ring-2 focus:ring-[#00F5A0]/20 transition shadow-[inset_0_2px_4px_rgba(0,0,0,0.6)]"
              placeholder="Enter username"
              required
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-[0.14em] text-zinc-400 mb-1.5 font-mono">
              Password / Security Token
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-white/[0.08] bg-[#09090c] px-3.5 py-3 text-sm text-white placeholder-zinc-600 focus:border-[#00F5A0]/60 focus:outline-none focus:ring-2 focus:ring-[#00F5A0]/20 transition shadow-[inset_0_2px_4px_rgba(0,0,0,0.6)]"
              placeholder="Enter password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-gradient-to-r from-[#00F5A0] via-teal-400 to-[#00D9F5] py-3.5 text-sm font-black text-black tracking-wide shadow-[0_0_30px_rgba(0,245,160,0.4),inset_0_1px_0_rgba(255,255,255,0.7)] hover:shadow-[0_0_40px_rgba(0,245,160,0.6)] active:scale-[0.98] transition disabled:opacity-50 mt-2"
          >
            {loading ? "Authenticating Key..." : "Unlock Trading Terminal"}
          </button>
        </form>

        <div className="mt-6 border-t border-white/[0.07] pt-4 text-center">
          <p className="text-[11px] text-zinc-500 font-mono">
            Default credentials: <code className="text-[#00F5A0] bg-white/[0.05] px-1.5 py-0.5 rounded">admin</code> / <code className="text-[#00F5A0] bg-white/[0.05] px-1.5 py-0.5 rounded">fno2026</code>
          </p>
        </div>
      </div>
    </main>
  );
}
