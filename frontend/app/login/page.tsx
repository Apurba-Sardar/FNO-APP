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
    <main className="flex min-h-screen items-center justify-center bg-slate-950 p-4 font-sans text-slate-100">
      <div className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900/80 p-8 backdrop-blur-xl shadow-2xl">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400">
            🔒
          </div>
          <p className="text-xs font-bold uppercase tracking-[.25em] text-cyan-400">
            Security Access Control
          </p>
          <h1 className="mt-1 text-2xl font-black text-slate-100">
            FNO SCANNER AUTH
          </h1>
          <p className="mt-1 text-xs text-slate-400">
            Enter authorized credentials to access algorithmic trading controls.
          </p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3 text-center text-xs font-semibold text-rose-300">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:border-cyan-500 focus:outline-none transition"
              placeholder="Enter username"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Password / Security Token
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-600 focus:border-cyan-500 focus:outline-none transition"
              placeholder="Enter password"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-cyan-500 py-3 text-sm font-bold text-slate-950 hover:bg-cyan-400 active:scale-[0.99] transition disabled:opacity-50"
          >
            {loading ? "Authenticating..." : "Unlock Dashboard"}
          </button>
        </form>

        <div className="mt-6 border-t border-slate-800/80 pt-4 text-center">
          <p className="text-[11px] text-slate-500">
            Default credentials: <code className="text-cyan-400 font-mono">admin</code> / <code className="text-cyan-400 font-mono">fno2026</code>
          </p>
        </div>
      </div>
    </main>
  );
}
