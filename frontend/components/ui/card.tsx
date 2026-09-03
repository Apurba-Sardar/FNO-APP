import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-800/90 bg-slate-900/65 p-3.5 shadow-[0_8px_30px_rgba(0,0,0,0.16)] backdrop-blur-sm sm:p-4",
        className,
      )}
      {...props}
    />
  );
}
