/**
 * Utility functions for user-friendly numbers, currency, and Indian Standard Time (IST) formatting.
 */

export function formatIST(ts: number | string | Date | undefined | null, includeSeconds = true): string {
  if (!ts) return "—";
  const date = ts instanceof Date ? ts : typeof ts === "number" ? new Date(ts) : new Date(ts);
  if (isNaN(date.getTime())) return "—";

  const options: Intl.DateTimeFormatOptions = {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  };

  if (includeSeconds) {
    options.second = "2-digit";
  }

  return date.toLocaleString("en-IN", options) + " IST";
}

export function formatISTTime(ts: number | string | Date | undefined | null): string {
  if (!ts) return "—";
  const date = ts instanceof Date ? ts : typeof ts === "number" ? new Date(ts) : new Date(ts);
  if (isNaN(date.getTime())) return "—";

  return date.toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  }) + " IST";
}

export function timeAgo(ts: number | string | Date | undefined | null): string {
  if (!ts) return "";
  const date = ts instanceof Date ? ts : typeof ts === "number" ? new Date(ts) : new Date(ts);
  if (isNaN(date.getTime())) return "";

  const diffSec = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (diffSec < 45) return "just now";
  if (diffSec < 90) return "1m ago";
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

export function money(value: unknown, maxDecimals = 4, minDecimals = 2): string {
  const num = Number(value ?? 0);
  if (isNaN(num)) return "0.00";
  return num.toLocaleString("en-IN", {
    maximumFractionDigits: maxDecimals,
    minimumFractionDigits: minDecimals,
  });
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return "0.00%";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(2)}%`;
}

export function scoreBadgeClass(score: number): { text: string; bg: string; border: string; label: string } {
  if (score >= 80) {
    return {
      text: "text-emerald-400",
      bg: "bg-emerald-500/15",
      border: "border-emerald-500/30",
      label: "Strong Breakout",
    };
  }
  if (score >= 70) {
    return {
      text: "text-cyan-400",
      bg: "bg-cyan-500/15",
      border: "border-cyan-500/30",
      label: "High Momentum",
    };
  }
  if (score >= 60) {
    return {
      text: "text-amber-300",
      bg: "bg-amber-500/15",
      border: "border-amber-500/30",
      label: "Moderate",
    };
  }
  return {
    text: "text-slate-400",
    bg: "bg-slate-800",
    border: "border-slate-700",
    label: "Consolidating",
  };
}
