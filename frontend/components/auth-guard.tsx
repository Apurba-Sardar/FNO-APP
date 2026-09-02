"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const isAuth = typeof window !== "undefined" && sessionStorage.getItem("fno_authenticated") === "true";
    setAuthenticated(isAuth);

    if (!isAuth && pathname !== "/login") {
      router.replace("/login");
    }
  }, [pathname, router]);

  if (pathname === "/login") {
    return <>{children}</>;
  }

  if (authenticated === null) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-slate-400">
        <div className="flex items-center gap-3">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-cyan-400 border-t-transparent"></div>
          <span className="text-sm font-semibold">Verifying session security...</span>
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return null;
  }

  return <>{children}</>;
}

export function logout() {
  if (typeof window !== "undefined") {
    sessionStorage.removeItem("fno_authenticated");
    window.location.href = "/login";
  }
}
